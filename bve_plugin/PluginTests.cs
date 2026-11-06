using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Mackoy.Bvets;
using JRController.Bve;

class PluginTests
{
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    static extern IntPtr CreateFileMapping(IntPtr file, IntPtr security, uint protect, uint high, uint low, string name);
    [DllImport("kernel32.dll")]
    static extern IntPtr MapViewOfFile(IntPtr handle, uint access, uint high, uint low, UIntPtr size);
    [DllImport("kernel32.dll")] static extern bool UnmapViewOfFile(IntPtr view);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    static IntPtr view;
    static List<string> events = new List<string>();
    static void Assert(bool value, string name) { if (!value) throw new Exception(name); }
    static void Publish(int notch, int rev, int buttons, int enabled, int age, int seq)
    {
        int[] packet = {seq, 0x4A524256, unchecked(Environment.TickCount-age), notch, rev, buttons, enabled, seq};
        Marshal.Copy(packet, 0, view, 8);
    }
    static int[][] Ranges(bool two) { return new int[][] {new int[]{-1,1},new int[]{0,two?5:0},new int[]{0,9},new int[]{-9,5}}; }
    static void Main()
    {
        try { Run(); }
        catch (Exception e) { Console.WriteLine(e.GetType().FullName); Console.WriteLine(e.Message); Environment.Exit(1); }
    }
    static void Run()
    {
        IntPtr map = CreateFileMapping(new IntPtr(-1), IntPtr.Zero, 4, 0, 32, "Local\\JRController.BVE.plugin-tests");
        view = MapViewOfFile(map, 6, 0, 0, new UIntPtr(32));
        Assert(view != IntPtr.Zero, "map");
        InputDevice plugin = new InputDevice();
        try
        {
            plugin.LeverMoved += delegate(object o, InputEventArgs e) { events.Add("L"+e.Axis+":"+e.Value); };
            plugin.KeyDown += delegate(object o, InputEventArgs e) { events.Add("D"+e.Axis+":"+e.Value); };
            plugin.KeyUp += delegate(object o, InputEventArgs e) { events.Add("U"+e.Axis+":"+e.Value); };
            plugin.Load(""); plugin.SetAxisRanges(Ranges(true)); plugin.Tick();
            Assert(events.Count == 0, "idle must not override keyboard");
            for (int n=-9; n<=5; n++)
            {
                plugin.SetAxisRanges(Ranges(true)); events.Clear(); Publish(n,1,0,1,0,2); plugin.Tick();
                Assert(events.Contains("L1:"+Math.Max(n,0)), "power "+n);
                Assert(events.Contains("L2:"+Math.Max(-n,0)), "brake "+n);
                Assert(events.Contains("L0:1"), "reverser");
            }
            events.Clear(); Publish(0,-1,15,1,0,4); plugin.Tick();
            Assert(events.Contains("D-1:0") && events.Contains("D-2:0") && events.Contains("D-2:2") && events.Contains("D-2:3"), "four buttons");
            int count=events.Count; plugin.Tick(); Assert(events.Count==count,"held buttons do not repeat");
            Publish(0,-1,0,1,0,6); plugin.Tick(); Assert(events.Contains("U-1:0"),"release");
            events.Clear(); Publish(5,1,0,1,0,7); plugin.Tick(); Assert(events.Count==0,"odd packet rejected");
            Publish(5,1,0,1,0,8); Marshal.WriteInt32(view,28,10); plugin.Tick(); Assert(events.Count==0,"torn packet rejected");
            Publish(5,1,0,1,1000,10); System.Threading.Thread.Sleep(510); plugin.Tick();
            Assert(events.Contains("L2:9") && events.Contains("L0:0"),"timeout EB");
            events.Clear(); plugin.Tick(); Assert(events.Count==0,"idle after timeout");
            Publish(3,1,1,1,0,12); plugin.Tick(); Assert(events.Contains("L1:3"),"reconnect");
            events.Clear(); Publish(3,1,1,0,0,14); plugin.Tick(); Assert(events.Contains("L2:9") && events.Contains("U-1:0"),"disabled EB and key release");
            plugin.SetAxisRanges(Ranges(false)); events.Clear(); Publish(-5,0,0,1,0,16); plugin.Tick();
            Assert(events.Contains("L3:-5"),"single handle");
            int[][] small=Ranges(true); small[1][1]=4; small[2][1]=8;
            plugin.SetAxisRanges(small); events.Clear(); Publish(5,0,0,1,0,18); plugin.Tick(); Assert(events.Contains("L1:4"),"power scaling");
            Publish(-8,0,0,1,0,20); plugin.Tick(); Assert(events.Contains("L2:7"),"service scaling excludes EB");
            Publish(-9,0,0,1,0,22); plugin.Tick(); Assert(events.Contains("L2:8"),"EB scaling");
            Console.WriteLine("PASS: all 15 notches, F/N/R, buttons, timeout, disabled, packet validation, scaling, single/two handle");
        }
        finally { plugin.Dispose(); UnmapViewOfFile(view); CloseHandle(map); }
    }
}
