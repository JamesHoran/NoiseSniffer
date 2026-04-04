import { useRef, useCallback, useState } from "react";
import "./App.css";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { SpectrumAnalyzer } from "./components/SpectrumAnalyzer";
import { RulesTab } from "./components/RulesTab";
import { useWebSocket } from "./hooks/useWebSocket";
import type { PacketMessage, WebSocketMessage } from "./hooks/useWebSocket";
import PacketStream from "./components/PacketStream";
import { Activity, Database, Shield } from "lucide-react";

const WS_URL = "ws://localhost:8000/ws";

function normalizeToDb(value: number): number {
  const clamped = Math.max(0, Math.min(1, value));
  return -100 + clamped * 100;
}

function App() {
  // 1. Use Refs instead of State for high-frequency data!
  const latestSpectrumRef = useRef<number[]>(Array(1024).fill(-100));
  const latestAnnotationsRef = useRef<Array<{ label: string; frequency: number }>>([]);
  const packetBufferRef = useRef<PacketMessage[]>([]);

  // 2. Silently update the buffers without re-rendering React
  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === "spectrum" && message.bins) {
      latestSpectrumRef.current = message.bins.map(normalizeToDb);

      if (message.annotations) {
        latestAnnotationsRef.current = message.annotations;
      }
    } else if (message.type === "packet") {
      // Add new packet to the front, and keep only the last 100 to prevent memory leaks
      packetBufferRef.current.unshift(message);
      if (packetBufferRef.current.length > 100) {
        packetBufferRef.current.pop();
      }
    }
  }, []);

  const [isMuted, setIsMuted] = useState(false);

  const toggleMute = async () => {
    const next = !isMuted;
    await fetch("http://localhost:8000/mute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ muted: next }),
    });
    setIsMuted(next);
  };

  const { isConnected } = useWebSocket<WebSocketMessage>(WS_URL, {
    onMessage: handleMessage,
    reconnectInterval: 3000,
    reconnectAttempts: 10,
  });

  return (
    <>
      <section id="center">
        {/* Header with connection status */}
        <div className="mb-6 flex items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-900/30">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">NoiseSniffer</h1>
              <p className="text-xs text-zinc-500">Real-time network audio visualization</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium flex items-center gap-2 px-3 py-1.5 rounded-lg ${isConnected ? "text-green-400 bg-green-950/30 border border-green-900/50" : "text-red-400 bg-red-950/30 border border-red-900/50"}`}>
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}></span>
              {isConnected ? "Live" : "Disconnected"}
            </span>
            <button
              onClick={toggleMute}
              className={`text-xs px-3 py-2 rounded-lg border font-medium transition-all ${
                isMuted
                  ? "border-red-900/50 text-red-400 hover:border-red-700 hover:bg-red-950/30"
                  : "border-zinc-700 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800/50"
              }`}
            >
              {isMuted ? "Unmute" : "Mute"}
            </button>
          </div>
        </div>

        <Tabs defaultValue="spectrum">
          <TabsList>
            <TabsTrigger value="spectrum" icon={<Activity className="h-4 w-4" />}>Spectrum</TabsTrigger>
            <TabsTrigger value="packets" icon={<Database className="h-4 w-4" />}>Packets</TabsTrigger>
            <TabsTrigger value="rules" icon={<Shield className="h-4 w-4" />}>Rules</TabsTrigger>
          </TabsList>

          <TabsContent value="spectrum">
            <SpectrumAnalyzer spectrumRef={latestSpectrumRef} annotationsRef={latestAnnotationsRef} />
          </TabsContent>

          <TabsContent value="packets">
            <PacketStream />
          </TabsContent>

          <TabsContent value="rules">
            <RulesTab />
          </TabsContent>
        </Tabs>
      </section>
    </>
  );
}

export default App;
