using System;
using System.Threading.Tasks;
using Microsoft.Identity.Client;
using MailKit;
using MailKit.Net.Imap;
using MailKit.Security;
using MimeKit;

class Program
{
    static async Task Main(string[] args)
    {
        string clientId = "4073be27-ca2d-454c-89b2-8731242fe31c"; 
        string[] scopes = new[] { "https://outlook.office.com/IMAP.AccessAsUser.All" };

        var app = PublicClientApplicationBuilder.Create(clientId)
            .WithAuthority(AadAuthorityAudience.PersonalMicrosoftAccount)
            .WithRedirectUri("http://localhost:8000")
            .Build();

        // 1. Opens browser popup for OAuth2 login
        var authResult = await app.AcquireTokenInteractive(scopes)
            .ExecuteAsync();

        // 2. Connect to Outlook IMAP
        using var client = new ImapClient();
        await client.ConnectAsync("outlook.office365.com", 993, SecureSocketOptions.SslOnConnect);

        var oauth2 = new SaslMechanismOAuth2(authResult.Account.Username, authResult.AccessToken);
        await client.AuthenticateAsync(oauth2);

        // 3. Open the Inbox
        await client.Inbox.OpenAsync(FolderAccess.ReadOnly);
        Console.WriteLine($"Connected! Total Inbox Messages: {client.Inbox.Count}\n");

        // 4. Fetch and display the last 10 messages (or fewer if total < 10)
        int fetchCount = Math.Min(10, client.Inbox.Count);
        int startIndex = client.Inbox.Count - fetchCount;

        Console.WriteLine($"--- Recent {fetchCount} Messages ---");

        for (int i = client.Inbox.Count - 1; i >= startIndex; i--)
        {
            MimeMessage message = await client.Inbox.GetMessageAsync(i);

            Console.WriteLine($"[Index {i}]");
            Console.WriteLine($"From:    {message.From}");
            Console.WriteLine($"Subject: {message.Subject}");
            Console.WriteLine($"Date:    {message.Date}");
            
            // Print a snippet of the text body (truncated to 100 chars)
            string bodySnippet = message.TextBody?.Trim().Replace("\r\n", " ").Replace("\n", " ") ?? "[No Text Body]";
            if (bodySnippet.Length > 100) bodySnippet = bodySnippet.Substring(0, 100) + "...";
            Console.WriteLine($"Preview: {bodySnippet}");
            
            Console.WriteLine(new string('-', 50));
        }

        // 5. Clean disconnect
        await client.DisconnectAsync(true);
    }
}