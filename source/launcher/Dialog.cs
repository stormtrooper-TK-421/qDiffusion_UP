using System;
using System.Windows.Forms;

namespace qDiffusion
{
    public partial class Dialog : Form
    {
        public Dialog()
        {
            InitializeComponent();
        }

        public void SetProgress(int value)
        {
            if (InvokeRequired)
            {
                Invoke(new Action<int>(SetProgress), value);
                return;
            }

            int clamped = Math.Max(progressBar.Minimum, Math.Min(progressBar.Maximum, value));
            progressBar.Value = clamped;
        }

        public void SetLabel(string value)
        {
            if (InvokeRequired)
            {
                Invoke(new Action<string>(SetLabel), value);
                return;
            }

            label.Text = value;
        }

        public void DoClose()
        {
            if (InvokeRequired)
            {
                Invoke(new Action(DoClose));
                return;
            }

            Close();
        }
    }
}
