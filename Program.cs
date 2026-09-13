using System;
using System.Net;
using System.Net.Mail;
using System.Net.Mime;
using System.Threading;
using System.ComponentModel;
using System.Net.PeerToPeer;

namespace Examples.SmtpExamples.Async
{
    public class SimpleAsynchronousExample
    {
        static bool mailSent = false;
        private static void SendCompletedCallback(object sender, AsyncCompletedEventArgs e)
        {
            // Get the unique identifier for this asynchronous operation.
            String token = (string)e.UserState;
            if (e.Cancelled) Console.WriteLine("[{0}] Send canceled.", token);
            if (e.Error != null) Console.WriteLine("[{0}] {1}", token, e.Error.ToString());
            else Console.WriteLine("Message sent.");
            mailSent = true;
        }
        public static void Main(string[] args)
        {
            string host = args[0];
            string username = args[1];
            string password = args[2];
            string sender = args[3];
            string recipient = args[4];
            int port = args[5] == null ? 25 : Convert.ToInt32(args[5]);
            bool EnableSsl = args[6] != null;
            string userState = "test message1";

            // Command-line argument must be the SMTP host.
            SmtpClient client = new SmtpClient(host); client.Port = port; client.EnableSsl = EnableSsl; 
            client.Credentials = (ICredentialsByHost)new System.Net.NetworkCredential(username, password);

            // Specify the email sender.
            // Create a mailing address that includes a UTF8 character
            // in the display name.
            MailAddress from = new MailAddress(sender, "sender: "+sender, System.Text.Encoding.UTF8);
            // Set destinations for the email message.
            MailAddress to = new MailAddress(recipient);
            // Specify the message content.
            MailMessage message = new MailMessage(from, to);
            message.Body = "This is a test email message sent by an application. ";
            // Include some non-ASCII characters in body and subject.
            string someArrows = new string(new char[] { '\u2190', '\u2191', '\u2192', '\u2193' });
            message.Body += Environment.NewLine + someArrows;
            message.BodyEncoding = System.Text.Encoding.UTF8;
            message.Subject = "test message" ;
            message.SubjectEncoding = System.Text.Encoding.UTF8;


            // Set the method that is called back when the send operation ends.
            client.SendCompleted += new SendCompletedEventHandler(SendCompletedCallback);

            // The userState can be any object that allows your callback
            // method to identify this send operation.
            // For this example, the userToken is a string constant.
            client.SendAsync(message, userState);

            Console.WriteLine("Sending message... press c to cancel mail. Press any other key to exit.");
            string answer = Console.ReadLine();
            // If the user canceled the send, and mail hasn't been sent yet,
            // then cancel the pending operation.
            if (answer.StartsWith("c") && mailSent == false) client.SendAsyncCancel();
            // Clean up.
            message.Dispose();

            Console.WriteLine("Goodbye.");
        }
    }
}