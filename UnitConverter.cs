// Unit Converter / calculator -- C# port of unit_converter.py.
//
// Same behaviour as the Python version, without the 9 MB interpreter: it
// targets .NET Framework 4.8, which is part of Windows 10/11, so the exe is
// a few tens of KB and needs nothing installed. Build with build_cs.bat,
// or by hand with the compiler that ships inside Windows:
//
//   %WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe -nologo -optimize+
//       -target:winexe -codepage:65001 -win32manifest:UnitConverter.manifest
//       -r:System.Windows.Forms.dll -r:System.Drawing.dll
//       -out:dist\UnitConverter.exe UnitConverter.cs
//
// That compiler only knows C# 5, so this file deliberately avoids newer
// syntax (string interpolation, => members, ?., tuples ...).
//
// Type a unit-aware expression and it evaluates to a base unit, then shows
// conversions within that dimension. Click any row (or its copy button) to
// copy; copying closes the app.
//
//     12mm+1ft-2in      -> 266 mm      (length, base = mm)
//     1ft 2in           -> 355.6 mm    (adjacent quantities add)
//     (3+2)*4in         -> 508 mm
//     72F               -> 22.22 C     (temperature, base = C)
//     5kg-200g          -> 10.582 lb   (mass, base = lb)
//     2gal+1qt          -> 8.5172 L    (volume, base = L)
//     3in3              -> 0.0492 L    (cubic units: in3, m^3, cm³ ...)
//     12mm/3mm          -> 4           (a ratio: dimensionless)
//     45                -> shows the "interpret as everything" table
//
// Extra units can be defined in unit_converter.ini next to the exe (a
// commented sample is written on first run).

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace UnitConverter
{
    // --- unit registry ----------------------------------------------------
    class LinearUnit
    {
        public readonly string Dim;
        public readonly double Factor;   // base_value = value * Factor
        public LinearUnit(string dim, double factor) { Dim = dim; Factor = factor; }
    }

    class TempUnit
    {
        public readonly Func<double, double> ToBase, FromBase;
        public TempUnit(Func<double, double> toBase, Func<double, double> fromBase)
        {
            ToBase = toBase; FromBase = fromBase;
        }
    }

    // Row of the conversion table: display label + registry key.
    struct Out
    {
        public readonly string Label, Key;
        public Out(string label, string key) { Label = label; Key = key; }
    }

    static class Units
    {
        // Base per dimension: length -> mm, mass -> lb, volume -> L.
        public static readonly Dictionary<string, LinearUnit> Linear =
            new Dictionary<string, LinearUnit>(StringComparer.Ordinal);

        // Temperature is affine, so it needs explicit to/from-base (base = C).
        public static readonly Dictionary<string, TempUnit> Temp =
            new Dictionary<string, TempUnit>(StringComparer.Ordinal)
        {
            { "c", new TempUnit(v => v, b => b) },
            { "f", new TempUnit(v => (v - 32) / 1.8, b => b * 1.8 + 32) },
            { "k", new TempUnit(v => v - 273.15, b => b + 273.15) },
        };

        public static readonly Out[] LengthOut = {
            new Out("mm", "mm"), new Out("cm", "cm"), new Out("m", "m"),
            new Out("in", "in"), new Out("ft", "ft"), new Out("yd", "yd"),
            new Out("thou", "thou") };
        public static readonly Out[] MassOut = {
            new Out("lb", "lb"), new Out("oz", "oz"), new Out("g", "g"),
            new Out("kg", "kg") };
        public static readonly Out[] VolumeOut = {
            new Out("mL", "ml"), new Out("L", "l"), new Out("fl oz", "floz"),
            new Out("cup", "cup"), new Out("pt", "pt"), new Out("qt", "qt"),
            new Out("gal", "gal"), new Out("in³", "in3"), new Out("ft³", "ft3") };
        public static readonly Out[] TempOut = {
            new Out("°C", "c"), new Out("°F", "f"), new Out("K", "k") };

        static void L(string dim, double factor, params string[] names)
        {
            foreach (string n in names) Linear[n] = new LinearUnit(dim, factor);
        }

        static Units()
        {
            // length (to mm)
            L("length", 1.0, "mm", "millimeter", "millimeters");
            L("length", 10.0, "cm", "centimeter");
            L("length", 1000.0, "m", "meter", "metre");
            L("length", 1000000.0, "km");
            L("length", 0.001, "um", "micron");
            L("length", 25.4, "in", "inch", "inches", "\"");
            L("length", 304.8, "ft", "foot", "feet", "'");
            L("length", 914.4, "yd", "yard");
            L("length", 0.0254, "thou", "mil");
            // mass / weight (to lb)
            L("mass", 1.0, "lb", "lbs", "pound", "pounds");
            L("mass", 0.0625, "oz", "ounce", "ounces");
            L("mass", 0.00220462262185, "g", "gram", "grams");
            L("mass", 2.20462262185, "kg", "kilogram");
            L("mass", 2.20462262185e-6, "mg");
            L("mass", 14.0, "st", "stone");
            L("mass", 2000.0, "ton");                    // US short ton
            L("mass", 2204.62262, "tonne", "t");         // metric tonne
            // volume / capacity (to L)
            L("volume", 1.0, "l", "liter", "liters", "litre", "litres");
            L("volume", 0.001, "ml", "milliliter", "millilitre", "cc");
            L("volume", 0.01, "cl");
            L("volume", 0.1, "dl");
            L("volume", 1000.0, "kl", "m3", "cbm");
            L("volume", 1e-6, "mm3");
            L("volume", 0.001, "cm3");
            L("volume", 0.016387064, "in3", "cuin");
            L("volume", 28.316846592, "ft3", "cuft");
            L("volume", 764.554857984, "yd3", "cuyd");
            // US liquid measure
            L("volume", 0.0295735295625, "floz", "fluidounce");
            L("volume", 0.00492892159375, "tsp", "teaspoon");
            L("volume", 0.01478676478125, "tbsp", "tablespoon");
            L("volume", 0.2365882365, "cup", "cups");
            L("volume", 0.473176473, "pt", "pint");
            L("volume", 0.946352946, "qt", "quart");
            L("volume", 3.785411784, "gal", "gallon", "gallons");
            L("volume", 158.987294928, "bbl");            // 42-gal oil barrel
            // Imperial liquid measure
            L("volume", 0.0284130625, "impfloz");
            L("volume", 0.56826125, "imppt");
            L("volume", 1.1365225, "impqt");
            L("volume", 4.54609, "impgal");
        }

        public static string FriendlyDim(string dim)
        {
            switch (dim)
            {
                case "length": return "length";
                case "mass": return "mass/weight";
                case "temperature": return "temperature";
                case "volume": return "volume";
                default: return "number";
            }
        }

        /// Canonical registry key for a unit as typed ("M^3" -> "m3").
        public static string Key(string unit)
        {
            string u = unit.Replace("°", "").Replace("µ", "u").Replace("^", "")
                           .Replace("³", "3").Replace("²", "2");
            return (u == "'" || u == "\"") ? u : u.ToLowerInvariant();
        }

        public static bool IsKnown(string unit)
        {
            string k = Key(unit);
            return Temp.ContainsKey(k) || Linear.ContainsKey(k);
        }

        public static Quantity ToQuantity(double value, string unit)
        {
            if (unit == null) return new Quantity(value, null);
            string k = Key(unit);
            TempUnit t;
            if (Temp.TryGetValue(k, out t)) return new Quantity(t.ToBase(value), "temperature");
            LinearUnit lu;
            if (Linear.TryGetValue(k, out lu)) return new Quantity(value * lu.Factor, lu.Dim);
            throw new EvalError("unknown unit '" + unit + "'");
        }

        public static double FromBase(double baseValue, string key)
        {
            return baseValue / Linear[key].Factor;
        }
    }

    /// A magnitude in its dimension's base unit. Dim == null is a plain number.
    class Quantity
    {
        public readonly double Base;
        public readonly string Dim;
        public Quantity(double b, string dim) { Base = b; Dim = dim; }
    }

    class EvalError : Exception
    {
        public EvalError(string msg) : base(msg) { }
    }

    // --- tokenizer --------------------------------------------------------
    class Token
    {
        public char Op;          // '\0' for a number token
        public double Value;
        public string Unit;      // null when the number had no unit
        public bool IsNum { get { return Op == '\0'; } }
    }

    static class Tokenizer
    {
        static bool IsUnitChar(char c)
        {
            return char.IsLetter(c) || c == '°' || c == '\'' || c == '"' || c == 'µ';
        }

        public static List<Token> Tokenize(string text)
        {
            var tokens = new List<Token>();
            int i = 0, n = text.Length;
            while (i < n)
            {
                char ch = text[i];
                if (char.IsWhiteSpace(ch)) { i++; continue; }
                if ("+-*/()".IndexOf(ch) >= 0)
                {
                    tokens.Add(new Token { Op = ch });
                    i++;
                    continue;
                }
                if (char.IsDigit(ch) || ch == '.')
                {
                    int j = i;
                    while (j < n && (char.IsDigit(text[j]) || text[j] == '.')) j++;
                    string num = text.Substring(i, j - i);
                    double value;
                    if (!double.TryParse(num, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
                        throw new EvalError("bad number '" + num + "'");
                    i = j;
                    // optional unit right after the number
                    int k = i;
                    while (k < n && IsUnitChar(text[k])) k++;
                    // a cubic/square marker may be glued on: in3, m^3, cm³.
                    // Only take it when it really forms a known unit, so
                    // "5ft2" still parses the old way (5 ft plus a bare 2).
                    if (k > i)
                    {
                        foreach (int extra in new[] { 2, 1 })
                        {
                            if (k + extra <= n && Units.IsKnown(text.Substring(i, k + extra - i)))
                            {
                                k += extra;
                                break;
                            }
                        }
                    }
                    string unit = k > i ? text.Substring(i, k - i) : null;
                    i = k;
                    tokens.Add(new Token { Value = value, Unit = unit });
                    continue;
                }
                throw new EvalError("unexpected character '" + ch + "'");
            }
            return tokens;
        }
    }

    // --- recursive-descent parser ----------------------------------------
    class Parser
    {
        readonly List<Token> toks;
        int pos;

        public Parser(List<Token> tokens) { toks = tokens; }

        Token Peek() { return pos < toks.Count ? toks[pos] : null; }
        Token Next() { return toks[pos++]; }

        static bool IsOp(Token t, string ops)
        {
            return t != null && !t.IsNum && ops.IndexOf(t.Op) >= 0;
        }

        public Quantity Parse()
        {
            Quantity v = Expr();
            if (Peek() != null) throw new EvalError("unexpected trailing input");
            return v;
        }

        Quantity Expr()
        {
            Quantity left = Term();
            while (true)
            {
                Token t = Peek();
                if (IsOp(t, "+-"))
                {
                    Next();
                    left = Ops.AddSub(left, Term(), t.Op);
                }
                else if (t != null && t.IsNum)         // adjacency -> implicit addition
                {
                    left = Ops.AddSub(left, Term(), '+');
                }
                else break;
            }
            return left;
        }

        Quantity Term()
        {
            Quantity left = Factor();
            while (true)
            {
                Token t = Peek();
                if (IsOp(t, "*/"))
                {
                    Next();
                    left = Ops.MulDiv(left, Factor(), t.Op);
                }
                else break;
            }
            return left;
        }

        Quantity Factor()
        {
            Token t = Peek();
            if (t == null) throw new EvalError("unexpected end of input");
            if (IsOp(t, "("))
            {
                Next();
                Quantity v = Expr();
                if (!IsOp(Peek(), ")")) throw new EvalError("missing ')'");
                Next();
                return v;
            }
            if (IsOp(t, "+-"))
            {
                Next();
                Quantity v = Factor();
                return t.Op == '-' ? new Quantity(-v.Base, v.Dim) : v;
            }
            if (t.IsNum)
            {
                Next();
                return Units.ToQuantity(t.Value, t.Unit);
            }
            throw new EvalError("expected a value");
        }
    }

    static class Ops
    {
        public static Quantity AddSub(Quantity a, Quantity b, char op)
        {
            // A number written with no unit is assumed to already be in the
            // base unit of whatever it's combined with: "12.7 + .5in" == 25.4 mm.
            if (a.Dim != null && b.Dim != null && a.Dim != b.Dim)
                throw new EvalError("can't add/subtract " + Units.FriendlyDim(a.Dim)
                                    + " and " + Units.FriendlyDim(b.Dim));
            string dim = a.Dim ?? b.Dim;
            return new Quantity(op == '+' ? a.Base + b.Base : a.Base - b.Base, dim);
        }

        public static Quantity MulDiv(Quantity a, Quantity b, char op)
        {
            if (op == '*')
            {
                if (a.Dim == null) return new Quantity(a.Base * b.Base, b.Dim);
                if (b.Dim == null) return new Quantity(a.Base * b.Base, a.Dim);
                throw new EvalError("can't multiply two units together");
            }
            // division
            if (b.Dim == null)
            {
                if (b.Base == 0) throw new EvalError("divide by zero");
                return new Quantity(a.Base / b.Base, a.Dim);
            }
            if (a.Dim == b.Dim)
            {
                if (b.Base == 0) throw new EvalError("divide by zero");
                return new Quantity(a.Base / b.Base, null);   // ratio -> plain number
            }
            throw new EvalError("can't divide " + Units.FriendlyDim(a.Dim)
                                + " by " + Units.FriendlyDim(b.Dim));
        }
    }

    // --- evaluation, formatting & conversion output ----------------------
    class Row
    {
        public readonly string Label, Value;
        public Row(string label, string value) { Label = label; Value = value; }
    }

    class Result
    {
        public string Headline;
        public List<Row> Rows = new List<Row>();
        public void Add(string label, string value) { Rows.Add(new Row(label, value)); }
    }

    static class Calc
    {
        const int Decimals = 4;

        /// Evaluate an expression; hadUnit tells whether any unit was typed.
        public static Quantity Evaluate(string text, out bool hadUnit)
        {
            List<Token> tokens = Tokenizer.Tokenize(text);
            if (tokens.Count == 0) throw new EvalError("empty");
            hadUnit = false;
            foreach (Token t in tokens) if (t.IsNum && t.Unit != null) hadUnit = true;
            return new Parser(tokens).Parse();
        }

        // Matches Python's fmt() except for results above ~1e11 with a
        // fractional part: .NET Framework prints at most 15 significant
        // digits there, where Python shows a few more digits of float noise.
        public static string Fmt(double value)
        {
            double r = Math.Round(value, Decimals);
            if (r == 0) return "0";                          // also swallows -0
            return r.ToString("0.####", CultureInfo.InvariantCulture);
        }

        static void AddLinear(Result res, double b, Out[] outs)
        {
            foreach (Out o in outs) res.Add(o.Label, Fmt(Units.FromBase(b, o.Key)));
        }

        public static Result ConversionsFor(Quantity q, bool hadUnit)
        {
            var res = new Result();
            switch (q.Dim)
            {
                case "length":
                    AddLinear(res, q.Base, Units.LengthOut);
                    res.Headline = "= " + Fmt(q.Base) + " mm  (length)";
                    return res;
                case "mass":
                    AddLinear(res, q.Base, Units.MassOut);
                    res.Headline = "= " + Fmt(q.Base) + " lb  (mass)";
                    return res;
                case "volume":
                    AddLinear(res, q.Base, Units.VolumeOut);
                    res.Headline = "= " + Fmt(q.Base) + " L  (volume)";
                    return res;
                case "temperature":
                    foreach (Out o in Units.TempOut)
                        res.Add(o.Label, Fmt(Units.Temp[o.Key].FromBase(q.Base)));
                    res.Headline = "= " + Fmt(q.Base) + " °C  (temperature)";
                    return res;
            }
            // dimensionless
            if (hadUnit)
            {
                // a ratio like 12mm/3mm -> just the number
                res.Add("value", Fmt(q.Base));
                res.Headline = "= " + Fmt(q.Base);
                return res;
            }
            // bare number: the "interpret as everything" table
            double v = q.Base;
            res.Add("mm → in", Fmt(v / 25.4));
            res.Add("in → mm", Fmt(v * 25.4));
            res.Add("°F → °C", Fmt((v - 32) / 1.8));
            res.Add("°C → °F", Fmt(v * 1.8 + 32));
            res.Add("g → oz", Fmt(v * 0.0352739619));
            res.Add("oz → g", Fmt(v * 28.349523125));
            res.Add("lb → kg", Fmt(v * 0.45359237));
            res.Add("kg → lb", Fmt(v * 2.20462262185));
            res.Add("L → gal", Fmt(v / 3.785411784));
            res.Add("gal → L", Fmt(v * 3.785411784));
            res.Headline = Fmt(v) + "  (no unit — showing all interpretations)";
            return res;
        }
    }

    // --- config (optional extra units) -----------------------------------
    static class Config
    {
        public const string IniName = "unit_converter.ini";

        public static void LoadCustomUnits(string iniPath)
        {
            if (!File.Exists(iniPath))
            {
                File.WriteAllText(iniPath,
                    "; Add your own units here. Factor converts TO the base unit.\r\n" +
                    "; Base units: length = mm, mass = lb, volume = L." +
                    "  (temperature is built in)\r\n" +
                    "[LENGTH]\r\n" +
                    "; point = 0.352778   ; typographic point -> mm\r\n" +
                    "[MASS]\r\n" +
                    "; grain = 0.000142857  ; grain -> lb\r\n" +
                    "[VOLUME]\r\n" +
                    "; drop = 0.00005      ; drop -> L\r\n",
                    new UTF8Encoding(false));
                return;
            }
            string[] lines;
            try { lines = File.ReadAllLines(iniPath, Encoding.UTF8); }
            catch (IOException) { return; }

            string dim = null;
            foreach (string raw in lines)
            {
                string line = raw.Trim();
                if (line.Length == 0 || line[0] == ';' || line[0] == '#') continue;
                if (line[0] == '[')
                {
                    int close = line.IndexOf(']');
                    string section = (close > 0 ? line.Substring(1, close - 1) : line.Substring(1))
                                     .Trim().ToUpperInvariant();
                    dim = section == "LENGTH" ? "length"
                        : section == "MASS" ? "mass"
                        : section == "VOLUME" ? "volume" : null;
                    continue;
                }
                if (dim == null) continue;
                int eq = line.IndexOf('=');
                if (eq < 0) eq = line.IndexOf(':');
                if (eq <= 0) continue;
                string alias = line.Substring(0, eq).Trim().ToLowerInvariant();
                string value = line.Substring(eq + 1);
                // Unlike Python's configparser, tolerate a trailing comment
                // ("pt = 0.3528  ; typographic point"), which the sample invites.
                int cmt = value.IndexOfAny(new[] { ';', '#' });
                if (cmt >= 0) value = value.Substring(0, cmt);
                double factor;
                if (double.TryParse(value.Trim(), NumberStyles.Float,
                                    CultureInfo.InvariantCulture, out factor))
                    Units.Linear[alias] = new LinearUnit(dim, factor);
            }
        }
    }

    // --- GUI --------------------------------------------------------------
    class ConverterForm : Form
    {
        static readonly Color Ok = ColorTranslator.FromHtml("#00aa55");
        static readonly Color Err = ColorTranslator.FromHtml("#cc0000");

        readonly TextBox entry;
        readonly Label headline;
        readonly FlowLayoutPanel rows;
        readonly float scale;          // 1.0 at 96 dpi, 1.5 at 144 dpi ...
        string firstValue;

        int Px(int px) { return (int)Math.Round(px * scale); }

        public ConverterForm()
        {
            using (Graphics g = CreateGraphics()) scale = g.DpiX / 96f;

            Text = "Unit Converter";
            TopMost = true;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.None;   // we scale by hand via Px()
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;
            MinimumSize = new Size(Px(300), Px(120));
            KeyPreview = true;
            Padding = new Padding(Px(8), Px(8), Px(8), Px(6));

            var stack = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                WrapContents = false,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = Padding.Empty,
            };
            Controls.Add(stack);

            var top = new FlowLayoutPanel
            {
                AutoSize = true, WrapContents = false, Margin = new Padding(0, 0, 0, Px(4)),
            };
            top.Controls.Add(new Label
            {
                Text = "Expression:", AutoSize = true, Margin = new Padding(0, Px(5), Px(6), 0),
            });
            entry = new TextBox { Font = new Font("Consolas", 12f), Width = Px(230) };
            entry.TextChanged += delegate { Recompute(); };
            top.Controls.Add(entry);
            stack.Controls.Add(top);

            headline = new Label
            {
                AutoSize = true, ForeColor = Ok,
                Font = new Font("Segoe UI", 10f, FontStyle.Bold),
                Margin = new Padding(0, 0, 0, Px(4)),
            };
            stack.Controls.Add(headline);

            rows = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown, WrapContents = false,
                AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 0, Px(4)),
            };
            stack.Controls.Add(rows);

            stack.Controls.Add(new Label
            {
                Text = "Enter to copy result · Esc to quit",
                ForeColor = Color.Gray, AutoSize = true, Margin = Padding.Empty,
            });

            KeyDown += OnKeyDown;
            Shown += delegate { entry.Focus(); };
            Recompute();
        }

        void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape)
            {
                e.SuppressKeyPress = true;
                Close();
            }
            else if (e.KeyCode == Keys.Return)
            {
                e.SuppressKeyPress = true;
                if (firstValue != null) Copy(firstValue);
            }
        }

        void Recompute()
        {
            rows.SuspendLayout();
            while (rows.Controls.Count > 0) rows.Controls[0].Dispose();

            string text = entry.Text.Trim();
            firstValue = null;
            if (text.Length == 0)
            {
                headline.Text = "";
                headline.ForeColor = Ok;
            }
            else
            {
                try
                {
                    bool hadUnit;
                    Quantity q = Calc.Evaluate(text, out hadUnit);
                    Result res = Calc.ConversionsFor(q, hadUnit);
                    headline.Text = res.Headline;
                    headline.ForeColor = Ok;
                    if (res.Rows.Count > 0) firstValue = res.Rows[0].Value;
                    foreach (Row r in res.Rows) AddRow(r.Label, r.Value);
                }
                catch (EvalError e)
                {
                    headline.Text = "⚠ " + e.Message;
                    headline.ForeColor = Err;
                }
            }
            rows.ResumeLayout();
        }

        void AddRow(string label, string value)
        {
            var row = new FlowLayoutPanel
            {
                AutoSize = true, WrapContents = false, Margin = new Padding(0, Px(1), 0, Px(1)),
            };
            row.Controls.Add(new Label
            {
                Text = label, Width = Px(80), Height = Px(24),
                TextAlign = ContentAlignment.MiddleLeft, Margin = Padding.Empty,
            });
            var val = new Label
            {
                Text = value, Width = Px(150), Height = Px(24),
                Font = new Font("Consolas", 11f), BackColor = Color.White,
                BorderStyle = BorderStyle.Fixed3D, TextAlign = ContentAlignment.MiddleLeft,
                Margin = new Padding(0, 0, Px(6), 0), Cursor = Cursors.Hand,
            };
            // click the value box itself to copy too
            val.Click += delegate { Copy(value); };
            row.Controls.Add(val);
            var btn = new Button
            {
                Text = "copy", Width = Px(52), Height = Px(24), Margin = Padding.Empty,
                TabStop = false,
            };
            btn.Click += delegate { Copy(value); };
            row.Controls.Add(btn);
            rows.Controls.Add(row);
        }

        void Copy(string value)
        {
            // SetText flushes to the OLE clipboard, so the text survives exit.
            try { Clipboard.SetText(value); }
            catch (Exception) { /* clipboard busy: nothing sensible to do */ }
            Close();                                  // copy closes the app
        }
    }

    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            string dir = Path.GetDirectoryName(Application.ExecutablePath);
            try { Config.LoadCustomUnits(Path.Combine(dir, Config.IniName)); }
            catch (Exception) { /* read-only folder etc.: run with built-ins */ }
            Application.Run(new ConverterForm());
        }
    }
}
