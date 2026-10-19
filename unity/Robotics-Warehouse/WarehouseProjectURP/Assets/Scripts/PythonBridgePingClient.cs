using System.Collections;
using System.IO;
using System.Net.Sockets;
using UnityEngine;

public class PythonBridgePingClient : MonoBehaviour
{
    [Header("Python bridge")]
    [Tooltip("Use 127.0.0.1 when the Python server runs on this computer.")]
    public string host = "127.0.0.1";

    public int port = 5000;

    [Tooltip("Seconds allowed for connecting to the Python server.")]
    public float connectTimeoutSeconds = 3f;

    private void Start()
    {
        StartCoroutine(PingPythonBridge());
    }

    private IEnumerator PingPythonBridge()
    {
        using (var client = new TcpClient())
        {
            var connectTask = client.ConnectAsync(host, port);
            var deadline = Time.realtimeSinceStartup + connectTimeoutSeconds;

            while (!connectTask.IsCompleted && Time.realtimeSinceStartup < deadline)
            {
                yield return null;
            }

            if (!connectTask.IsCompleted)
            {
                Debug.LogError($"Python bridge connection timed out after {connectTimeoutSeconds:0.0} seconds ({host}:{port}).");
                yield break;
            }

            if (connectTask.IsFaulted || connectTask.IsCanceled)
            {
                var message = connectTask.Exception?.GetBaseException().Message ?? "connection was canceled";
                Debug.LogError($"Python bridge connection failed ({host}:{port}): {message}");
                yield break;
            }

            try
            {
                using (var stream = client.GetStream())
                using (var writer = new StreamWriter(stream))
                using (var reader = new StreamReader(stream))
                {
                    stream.ReadTimeout = 3000;
                    writer.AutoFlush = true;
                    writer.WriteLine("PING");
                    var response = reader.ReadLine();

                    if (response == "PONG")
                    {
                        Debug.Log($"Python bridge health check passed ({host}:{port}): PONG");
                    }
                    else
                    {
                        Debug.LogError($"Python bridge returned unexpected response: {response ?? "<connection closed>"}");
                    }
                }
            }
            catch (IOException exception)
            {
                Debug.LogError($"Python bridge health check failed ({host}:{port}): {exception.Message}");
            }
            catch (SocketException exception)
            {
                Debug.LogError($"Python bridge socket error ({host}:{port}): {exception.Message}");
            }
        }
    }
}
