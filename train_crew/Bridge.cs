using System;
using System.Diagnostics;
using System.Threading;
using System.Web.Script.Serialization;
using TrainCrew;

// Uses the documented SDK only; the game's files and DLL are not patched.
static class Bridge
{
    static readonly object Sync = new object();
    static readonly Stopwatch Clock = Stopwatch.StartNew();
    static readonly InputAction[] Actions = {
        InputAction.HornAir, InputAction.HornEle, InputAction.EBReset, InputAction.Buzzer
    };
    static int notch = -8, reverser, buttons;
    static int lastNotch = int.MinValue, lastReverser = int.MinValue, lastButtons = -1;
    static long heartbeat = -2000;
    static string lastScreen;
    static bool closed;

    static void Apply(bool stopping)
    {
        int n = stopping || Clock.ElapsedMilliseconds - heartbeat > 1000 ? -8 : notch;
        int r = n == -8 && (stopping || Clock.ElapsedMilliseconds - heartbeat > 1000) ? 0 : reverser;
        int b = stopping || Clock.ElapsedMilliseconds - heartbeat > 1000 ? 0 : buttons;
        var state = TrainCrewInput.GetTrainState();
        string screen = TrainCrewInput.gameState.gameScreen.ToString();
        bool changedScreen = screen != lastScreen;
        if (n != lastNotch || changedScreen) TrainCrewInput.SetNotch(n);
        if (r != lastReverser || changedScreen) TrainCrewInput.SetReverser(r);
        for (int i = 0; i < Actions.Length; i++)
            if (((b ^ lastButtons) & (1 << i)) != 0 || changedScreen)
                TrainCrewInput.SetButton(Actions[i], (b & (1 << i)) != 0);
        lastNotch = n; lastReverser = r; lastButtons = b; lastScreen = screen;
    }

    static int Main()
    {
        Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        Console.InputEncoding = new System.Text.UTF8Encoding(false);
        Timer timer = null;
        try
        {
            TrainCrewInput.Init();
            timer = new Timer(delegate {
                lock (Sync) {
                    if (closed) return;
                    try { Apply(false); }
                    catch (Exception e) { Console.Error.WriteLine(e.Message); }
                }
            }, null, 0, 20);
            Console.WriteLine("READY");
            string line;
            while ((line = Console.ReadLine()) != null && line != "QUIT")
            {
                lock (Sync)
                {
                    if (line == "?") {
                        var s = TrainCrewInput.GetTrainState();
                        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                            screen = TrainCrewInput.gameState.gameScreen.ToString(),
                            power = s.Pnotch, brake = s.Bnotch, reverser = s.Reverser,
                            speed = s.Speed, diagram = s.diaName
                        }));
                        continue;
                    }
                    string[] parts = line.Split(' ');
                    int n, r, b;
                    if (parts.Length != 3 || !int.TryParse(parts[0], out n) ||
                        !int.TryParse(parts[1], out r) || !int.TryParse(parts[2], out b) ||
                        n < -8 || n > 5 || r < -1 || r > 1 || b < 0 || b > 15)
                        throw new ArgumentException("Invalid controller report");
                    notch = n; reverser = r; buttons = b; heartbeat = Clock.ElapsedMilliseconds;
                }
            }
            return 0;
        }
        catch (Exception e) { Console.WriteLine("ERROR " + e); return 1; }
        finally
        {
            if (timer != null) timer.Dispose();
            lock (Sync) {
                closed = true;
                try { Apply(true); } catch { }
                try { TrainCrewInput.Dispose(); } catch { }
            }
        }
    }
}
