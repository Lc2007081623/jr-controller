using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Mackoy.Bvets;

[assembly: System.Reflection.AssemblyTitle("JR Controller")]
[assembly: System.Reflection.AssemblyProduct("JR Controller")]
[assembly: System.Reflection.AssemblyDescription("JR Controller BVE 5/6 input device")]
[assembly: System.Reflection.AssemblyCompany("JR Controller")]
[assembly: System.Reflection.AssemblyVersion("0.5.0.0")]

namespace JRController.Bve
{
    // CLR 2.0/.NET 3.5 compatible; the same source also builds for BVE 6.
    public sealed class InputDevice : IInputDevice
    {
#if TEST
        const string MapName = "Local\\JRController.BVE.plugin-tests";
#else
        const string MapName = "Local\\JRController.BVE.v1";
#endif
        const uint Magic = 0x4A524256;
        IntPtr mapping, view;
        bool active, hasRanges;
        uint lastTick;
        int powerMax, brakeMax, powerMin;
        bool twoHandle;
        int previousPower = int.MinValue, previousBrake = int.MinValue;
        int previousCombined = int.MinValue, previousReverser = int.MinValue, buttons;
        readonly int[] keyAxes = { -1, -2, -2, -2 };
        readonly int[] keyValues = { 0, 0, 2, 3 };

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr OpenFileMapping(uint access, bool inherit, string name);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr MapViewOfFile(IntPtr handle, uint access, uint high, uint low, UIntPtr size);
        [DllImport("kernel32.dll")]
        static extern bool UnmapViewOfFile(IntPtr address);
        [DllImport("kernel32.dll")]
        static extern bool CloseHandle(IntPtr handle);

        public event InputEventHandler LeverMoved;
        public event InputEventHandler KeyDown;
        public event InputEventHandler KeyUp;

        public void Load(string settingsPath) { }

        public void SetAxisRanges(int[][] ranges)
        {
            if (ranges == null || ranges.Length < 4) { hasRanges = false; return; }
            for (int i = 0; i < 4; i++)
                if (ranges[i] == null || ranges[i].Length < 2) { hasRanges = false; return; }
            twoHandle = ranges[1][1] > 0;
            powerMax = twoHandle ? ranges[1][1] : ranges[3][1];
            brakeMax = twoHandle ? ranges[2][1] : -ranges[3][0];
            powerMin = twoHandle ? ranges[1][0] : 0;
            hasRanges = powerMax > 0 && powerMax <= 32 && brakeMax >= 2 && brakeMax <= 32;
            previousPower = previousBrake = previousCombined = previousReverser = int.MinValue;
        }

        public void Tick()
        {
            if (!hasRanges) return;
            uint now = unchecked((uint)Environment.TickCount);
            if (view == IntPtr.Zero)
            {
                mapping = OpenFileMapping(4, false, MapName);
                if (mapping != IntPtr.Zero)
                {
                    view = MapViewOfFile(mapping, 4, 0, 0, new UIntPtr(32));
                    if (view == IntPtr.Zero) { CloseHandle(mapping); mapping = IntPtr.Zero; }
                }
            }
            if (view != IntPtr.Zero)
            {
                byte[] data = new byte[32];
                Marshal.Copy(view, data, 0, data.Length);
                uint seq = BitConverter.ToUInt32(data, 0);
                uint tick = BitConverter.ToUInt32(data, 8);
                int notch = BitConverter.ToInt32(data, 12);
                int reverser = BitConverter.ToInt32(data, 16);
                int mask = BitConverter.ToInt32(data, 20);
                int enabled = BitConverter.ToInt32(data, 24);
                // Both sequence copies plus a second read reject concurrent writes.
                bool valid = (seq & 1) == 0 && seq == BitConverter.ToUInt32(data, 28)
                    && seq == unchecked((uint)Marshal.ReadInt32(view))
                    && BitConverter.ToUInt32(data, 4) == Magic
                    && unchecked(now - tick) <= 500 && notch >= -9 && notch <= 5
                    && reverser >= -1 && reverser <= 1 && mask >= 0 && mask <= 15
                    && (enabled == 0 || enabled == 1);
                if (valid)
                {
                    if (enabled == 0) { Release(); return; }
                    active = true; lastTick = tick;
                    Apply(notch, reverser, mask);
                    return;
                }
            }
            if (active && unchecked(now - lastTick) > 500) Release();
        }

        static int Scale(int value, int sourceMax, int targetMax)
        {
            return value == 0 ? 0 : Math.Max(1, (value * targetMax + sourceMax / 2) / sourceMax);
        }

        void Apply(int notch, int reverser, int mask)
        {
            int power = notch > 0 ? Scale(notch, 5, powerMax) : 0;
            int brake = notch == -9 ? brakeMax : notch < 0 ? Scale(-notch, 8, brakeMax - 1) : 0;
            if (twoHandle)
            {
                Emit(1, Math.Max(powerMin, power), ref previousPower);
                Emit(2, brake, ref previousBrake);
            }
            else Emit(3, brake > 0 ? -brake : power, ref previousCombined);
            Emit(0, reverser, ref previousReverser);
            for (int i = 0; i < 4; i++)
            {
                int bit = 1 << i;
                if ((mask & bit) == (buttons & bit)) continue;
                InputEventHandler handler = (mask & bit) != 0 ? KeyDown : KeyUp;
                if (handler != null) handler(this, new InputEventArgs(keyAxes[i], keyValues[i]));
            }
            buttons = mask;
        }

        void Emit(int axis, int value, ref int previous)
        {
            if (value == previous) return;
            InputEventHandler handler = LeverMoved;
            if (handler != null) { handler(this, new InputEventArgs(axis, value)); previous = value; }
        }

        void Release()
        {
            if (!active) return;
            // Lost hardware/bridge must remove traction and apply EB, not leave a moving train coasting.
            Apply(-9, 0, 0);
            active = false;
            previousPower = previousBrake = previousCombined = previousReverser = int.MinValue;
        }

        public void Configure(IWin32Window owner)
        {
            MessageBox.Show(owner,
                "在 JR 控制器程序中选择 BVE 5/6 模式。\n主手柄 P1-P5 / B1-B8 / EB，换向器 F/N/R。\nA 鸣笛，B ATS确认，X EB确认，Y ATS复位。\n断开后紧急制动；重新连接后跟随实体位置。",
                "JR Controller · BVE 5/6");
        }

        public void Dispose()
        {
            Release();
            if (view != IntPtr.Zero) { UnmapViewOfFile(view); view = IntPtr.Zero; }
            if (mapping != IntPtr.Zero) { CloseHandle(mapping); mapping = IntPtr.Zero; }
        }
    }
}
