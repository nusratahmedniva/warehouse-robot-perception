using System;
using System.Collections.Concurrent;
using System.Threading;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace WarehouseRobot.Bridge
{
    /// <summary>
    /// JPEG-encodes GPU readbacks on a background thread (ImageConversion.EncodeArrayToJPG and JsonUtility.ToJson
    /// are thread-safe), frames the message and queues it on the connection. Errors are queued for the main thread.
    /// </summary>
    public sealed class FrameEncoder : IDisposable
    {
        public class Job
        {
            public byte[] Rgba;            // RGBA32 pixels from AsyncGPUReadback, Unity row order (row 0 = bottom)
            public int Width, Height;
            public bool FlipRows;
            public int Quality;
            public Func<int, string> HeaderForImageSize; // builds the header JSON once the JPEG size is known
            public Action Done;            // called on the encoder thread when the job is finished (sent or failed)
        }

        readonly BlockingCollection<Job> jobs = new BlockingCollection<Job>(new ConcurrentQueue<Job>());
        readonly ConcurrentQueue<string> errors = new ConcurrentQueue<string>();
        readonly BridgeConnection connection;
        readonly Thread thread;
        readonly CancellationTokenSource stop = new CancellationTokenSource();

        public FrameEncoder(BridgeConnection connection)
        {
            this.connection = connection;
            thread = new Thread(Run) { IsBackground = true, Name = "RobotBridge.Encode" };
            thread.Start();
        }

        public void Enqueue(Job job) => jobs.Add(job);

        public bool TryGetError(out string error) => errors.TryDequeue(out error);

        void Run()
        {
            try
            {
                while (true)
                {
                    var job = jobs.Take(stop.Token);
                    try
                    {
                        if (job.FlipRows) FlipRows(job.Rgba, job.Width, job.Height);
                        byte[] jpg = ImageConversion.EncodeArrayToJPG(job.Rgba, GraphicsFormat.R8G8B8A8_UNorm,
                            (uint)job.Width, (uint)job.Height, 0, job.Quality);
                        connection.Send(BridgeProtocol.Frame(job.HeaderForImageSize(jpg.Length), jpg), isFrame: true);
                    }
                    catch (Exception ex)
                    {
                        errors.Enqueue(ex.Message);
                    }
                    finally
                    {
                        job.Done?.Invoke();
                    }
                }
            }
            catch (OperationCanceledException) { }
        }

        static void FlipRows(byte[] rgba, int width, int height)
        {
            int row = width * 4;
            var tmp = new byte[row];
            for (int top = 0, bottom = height - 1; top < bottom; top++, bottom--)
            {
                Buffer.BlockCopy(rgba, top * row, tmp, 0, row);
                Buffer.BlockCopy(rgba, bottom * row, rgba, top * row, row);
                Buffer.BlockCopy(tmp, 0, rgba, bottom * row, row);
            }
        }

        public void Dispose()
        {
            stop.Cancel();
            thread.Join(2000);
        }
    }
}
