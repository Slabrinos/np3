#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Google.Apis.Auth.OAuth2;
using Google.Apis.Gmail.v1;
using Google.Apis.Services;
using Google.Apis.Util.Store;

// Aliases to eliminate name collisions between WinForms and Google API
using GmailMessage = Google.Apis.Gmail.v1.Data.Message;
using WinFormLabel = System.Windows.Forms.Label;

namespace GmailDesktopApp
{
    public class Form1 : Form
    {
        private static readonly string[] Scopes = { GmailService.Scope.GmailReadonly };
        private static readonly string ApplicationName = "Gmail C# Desktop App";

        private Button btnAuthorize = null!;
        private WinFormLabel lblStatus = null!;
        private DataGridView dgvEmails = null!;
        private GmailService? _gmailService;

        public Form1()
        {
            InitializeCustomComponents();
        }

        private void InitializeCustomComponents()
        {
            this.Text = "Gmail Viewer";
            this.Size = new System.Drawing.Size(800, 500);

            btnAuthorize = new Button
            {
                Text = "Authorize & Load Emails",
                Location = new System.Drawing.Point(20, 20),
                Size = new System.Drawing.Size(180, 40)
            };
            btnAuthorize.Click += btnAuthorize_Click;

            lblStatus = new WinFormLabel
            {
                Text = "Click 'Authorize' to log in with your Gmail account.",
                Location = new System.Drawing.Point(220, 30),
                AutoSize = true
            };

            dgvEmails = new DataGridView
            {
                Location = new System.Drawing.Point(20, 80),
                Size = new System.Drawing.Size(740, 350),
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                Visible = false
            };

            this.Controls.Add(btnAuthorize);
            this.Controls.Add(lblStatus);
            this.Controls.Add(dgvEmails);
        }

        private async void btnAuthorize_Click(object? sender, EventArgs e)
        {
            btnAuthorize.Enabled = false;
            lblStatus.Text = "Opening browser for authorization...";

            try
            {
                // Run auth on a background thread to prevent UI freezing
                UserCredential credential = await Task.Run(async () =>
                {
                    using (var stream = new FileStream("credentials.json", FileMode.Open, FileAccess.Read))
                    {
                        string credPath = "token.json";

                        // LocalServerCodeReceiver explicitly forces local desktop auth handling in VS Code
                        return await GoogleWebAuthorizationBroker.AuthorizeAsync(
                            GoogleClientSecrets.FromStream(stream).Secrets,
                            Scopes,
                            "user",
                            CancellationToken.None,
                            new FileDataStore(credPath, true),
                            new LocalServerCodeReceiver());
                    }
                });

                lblStatus.Text = "Successfully authorized! Loading emails...";

                _gmailService = new GmailService(new BaseClientService.Initializer()
                {
                    HttpClientInitializer = credential,
                    ApplicationName = ApplicationName,
                });

                await LoadUserEmailsAsync();

                lblStatus.Text = "Emails loaded successfully.";
                btnAuthorize.Visible = false;
                dgvEmails.Visible = true;
            }
            catch (Exception ex)
            {
                lblStatus.Text = $"Error: {ex.Message}";
                btnAuthorize.Enabled = true;
            }
        }

        private async Task LoadUserEmailsAsync()
        {
            if (_gmailService == null) return;

            var listRequest = _gmailService.Users.Messages.List("me");
            listRequest.MaxResults = 10;
            listRequest.Q = "label:INBOX";

            var listResponse = await listRequest.ExecuteAsync();
            var emailList = new List<EmailDisplayItem>();

            if (listResponse.Messages != null && listResponse.Messages.Count > 0)
            {
                foreach (var msgSummary in listResponse.Messages)
                {
                    var msgRequest = _gmailService.Users.Messages.Get("me", msgSummary.Id);
                    msgRequest.Format = UsersResource.MessagesResource.GetRequest.FormatEnum.Full;
                    
                    GmailMessage message = await msgRequest.ExecuteAsync();

                    string subject = "(No Subject)";
                    string from = "Unknown";
                    string date = "";

                    if (message.Payload?.Headers != null)
                    {
                        foreach (var header in message.Payload.Headers)
                        {
                            if (header.Name == "Subject") subject = header.Value;
                            if (header.Name == "From") from = header.Value;
                            if (header.Name == "Date") date = header.Value;
                        }
                    }

                    emailList.Add(new EmailDisplayItem
                    {
                        From = from,
                        Subject = subject,
                        Date = date
                    });
                }
            }

            dgvEmails.DataSource = emailList;
        }
    }

    public class EmailDisplayItem
    {
        public string From { get; set; } = string.Empty;
        public string Subject { get; set; } = string.Empty;
        public string Date { get; set; } = string.Empty;
    }
}