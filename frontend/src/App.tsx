import { useRef, useCallback, useState } from "react";
import "./App.css";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { SpectrumAnalyzer } from "./components/SpectrumAnalyzer";
import { RulesTab } from "./components/RulesTab";
import { useWebSocket } from "./hooks/useWebSocket";
import type { PacketMessage, WebSocketMessage } from "./hooks/useWebSocket";
import PacketStream from "./components/PacketStream";
import { Activity, Database, Shield, Volume2, VolumeX, Wifi, WifiOff } from "lucide-react";

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
      {/* Header with connection status - full width */}
      <nav className="sticky top-0 z-50 w-screen left-0 h-20 bg-zinc-950/80 backdrop-blur-xl border-b border-zinc-800/50">
        <div className="w-full h-full px-6">
          <div className="flex items-center justify-between h-full">
          {/* Logo and title */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-xl blur-lg opacity-50"></div>
              <div className="relative h-12 w-12 rounded-xl bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg">
                <Activity className="h-6 w-6 text-white" />
              </div>
            </div>
            <div className="flex flex-col justify-center">
              <h1 className="text-lg font-extrabold text-zinc-100 tracking-tight leading-none">
                NoiseSniffer
              </h1>
            </div>
          </div>

          {/* Status and controls */}
          <div className="flex items-center gap-3">
            {/* Connection status */}
            <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all ${
              isConnected
                ? "bg-green-950/30 border-green-900/50 text-green-400"
                : "bg-red-950/30 border-red-900/50 text-red-400"
            }`}>
              {isConnected ? (
                <>
                  <Wifi className="h-4 w-4 animate-pulse" />
                  <span className="text-sm font-medium">Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-4 w-4" />
                  <span className="text-sm font-medium">Offline</span>
                </>
              )}
            </div>

            {/* Mute button */}
            <button
              onClick={toggleMute}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl border font-medium transition-all ${
                isMuted
                  ? "bg-red-950/30 border-red-900/50 text-red-400 hover:border-red-700 hover:bg-red-950/50"
                  : "bg-zinc-800/50 border-zinc-700 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800"
              }`}
              title={isMuted ? "Unmute audio" : "Mute audio"}
            >
              {isMuted ? (
                <>
                  <VolumeX className="h-4 w-4" />
                  <span className="text-sm">Muted</span>
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4" />
                  <span className="text-sm">Audio On</span>
                </>
              )}
            </button>
          </div>
          </div>
        </div>
      </nav>

      {/* Main content area - constrained width */}
      <main className="w-full max-w-7xl mx-auto px-6 py-6">
        <Tabs defaultValue="spectrum" className="w-full">
          <TabsList>
            <TabsTrigger value="spectrum" icon={<Activity className="h-4 w-4" />}>
              Spectrum
            </TabsTrigger>
            <TabsTrigger value="packets" icon={<Database className="h-4 w-4" />}>
              Packets
            </TabsTrigger>
            <TabsTrigger value="rules" icon={<Shield className="h-4 w-4" />}>
              Rules
            </TabsTrigger>
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
      </main>
    </>
  );
}

export default App;
