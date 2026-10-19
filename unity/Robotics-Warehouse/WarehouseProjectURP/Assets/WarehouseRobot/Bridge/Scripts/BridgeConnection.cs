using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.Sockets;
using System.Threading;

namespace WarehouseRobot.Bridge
{
    public enum BridgeEventKind { Connected, Disconnected, Message }

    public class BridgeEvent
    {
        public BridgeEventKind Kind;
        public RawMessage Message;
        public string Text;
    }

    /// <summary>
    /// TCP client on background threads: one thread connects (and reconnects every reconnect interval) and reads
    /// messages; a second thread writes queued messages while connected. The main thread talks to it only through
    /// thread-safe queues: Send() to write, TryDequeue() to read events. No Unity API is called here except the
    /// thread-safe JsonUtility inside BridgeProtocol.Read.
    /// </summary>
    public sealed class BridgeConnection : IDisposable
    {
        readonly string host;
        readonly int port;
        readonly int maxHeaderBytes, maxAttachmentBytes;
        readonly int reconnectMs, connectTimeoutMs;
        readonly ConcurrentQueue<BridgeEvent> events = new ConcurrentQueue<BridgeEvent>();
        readonly BlockingCollection<OutItem> outgoing = new BlockingCollection<OutItem>(new ConcurrentQueue<OutItem>());
        readonly Thread thread;
        volatile bool stopping;
        volatile bool connected;
        volatile TcpClient client;
        int pendingFrames;

        volatile string lastConnectError;

        public bool Connected => connected;
        /// <summary>Why the last connection attempt failed (null after a successful connect).</summary>
        public string LastConnectError => lastConnectError;
        public string Endpoint => host + ":" + port;
        /// <summary>Frame messages queued but not yet written (the caller drops new frames above a limit).</summary>
        public int PendingFrames => Volatile.Read(ref pendingFrames);

        public BridgeConnection(string host, int port, int maxHeaderBytes, int maxAttachmentBytes, float reconnectS, float connectTimeoutS)
        {
            this.host = host;
            this.port = port;
            this.maxHeaderBytes = maxHeaderBytes;
            this.maxAttachmentBytes = maxAttachmentBytes;
            reconnectMs = (int)(reconnectS * 1000f);
            connectTimeoutMs = (int)(connectTimeoutS * 1000f);
            thread = new Thread(Run) { IsBackground = true, Name = "RobotBridge.Net" };
            thread.Start();
        }

        public bool TryDequeue(out BridgeEvent e) => events.TryDequeue(out e);

        /// <summary>Queue a framed message; dropped if not connected. Frames count toward PendingFrames.</summary>
        public void Send(byte[] framed, bool isFrame = false)
        {
            if (!connected || stopping) return;
            if (isFrame) Interlocked.Increment(ref pendingFrames);
            outgoing.Add(new OutItem { Data = framed, IsFrame = isFrame });
        }

        struct OutItem
        {
            public byte[] Data;
            public bool IsFrame;
        }

        void Run()
        {
            while (!stopping)
            {
                var c = new TcpClient { NoDelay = true };
                string reason = null;
                Thread writer = null;
                var stopWriter = new CancellationTokenSource();
                try
                {
                    if (!c.ConnectAsync(host, port).Wait(connectTimeoutMs) || !c.Connected)
                        throw new SocketException((int)SocketError.TimedOut);
                    client = c;
                    lastConnectError = null;
                    var stream = c.GetStream();
                    Drain();
                    connected = true;
                    events.Enqueue(new BridgeEvent { Kind = BridgeEventKind.Connected, Text = Endpoint });
                    writer = new Thread(() => WriteLoop(stream, stopWriter.Token)) { IsBackground = true, Name = "RobotBridge.Send" };
                    writer.Start();
                    while (!stopping)
                    {
                        var msg = BridgeProtocol.Read(stream, maxHeaderBytes, maxAttachmentBytes);
                        if (msg == null) { reason = "server closed the connection"; break; }
                        msg.ReceivedTicks = Stopwatch.GetTimestamp();
                        events.Enqueue(new BridgeEvent { Kind = BridgeEventKind.Message, Message = msg });
                    }
                }
                catch (BridgeFramingException ex)
                {
                    reason = ex.GetType().Name + ": " + ex.Message;
                }
                catch (Exception ex)
                {
                    reason = ex is AggregateException ae && ae.InnerException != null ? ae.InnerException.Message : ex.Message;
                }
                finally
                {
                    bool wasConnected = connected;
                    connected = false;
                    stopWriter.Cancel();
                    client = null;
                    c.Close();
                    writer?.Join(1000);
                    Drain();
                    if (wasConnected)
                        events.Enqueue(new BridgeEvent { Kind = BridgeEventKind.Disconnected, Text = stopping ? "stopped" : (reason ?? "closed") });
                    else
                        lastConnectError = reason; // failed attempt: shown in the panel, not logged every second
                }
                for (int waited = 0; waited < reconnectMs && !stopping; waited += 50) Thread.Sleep(50);
            }
        }

        void WriteLoop(NetworkStream stream, CancellationToken token)
        {
            try
            {
                while (!token.IsCancellationRequested)
                {
                    var item = outgoing.Take(token);
                    stream.Write(item.Data, 0, item.Data.Length);
                    if (item.IsFrame) Interlocked.Decrement(ref pendingFrames);
                }
            }
            catch (OperationCanceledException) { }
            catch (Exception)
            {
                client?.Close(); // the read loop then ends and reports the disconnect
            }
        }

        void Drain()
        {
            while (outgoing.TryTake(out _)) { }
            Interlocked.Exchange(ref pendingFrames, 0);
        }

        public void Dispose()
        {
            stopping = true;
            connected = false;
            client?.Close();
            thread.Join(2000);
        }
    }
}
