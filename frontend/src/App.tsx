import { useRef, useCallback, useState } from "react";
import "./App.css";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { SpectrumAnalyzer } from "./components/SpectrumAnalyzer";
import { RulesTab } from "./components/RulesTab";
// Assuming you have a PacketTable component for the left side of your sketch
// import { PacketTable } from "./components/PacketTable";
import { useWebSocket } from "./hooks/useWebSocket";
import type { SpectrumMessage, PacketMessage } from "./hooks/useWebSocket";
import PacketStream from "./components/PacketStream";

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
  const handleMessage = useCallback((message: any) => {
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

  const { isConnected } = useWebSocket<any>(WS_URL, {
    onMessage: handleMessage,
    reconnectInterval: 3000,
    reconnectAttempts: 10,
  });

  return (
    <>
      <section id="center">
        {/* Header with connection status */}
        <div className="mb-4 flex items-center justify-between px-4">
          <h1 className="text-2xl font-bold text-white">NoiseSniffer</h1>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium flex items-center gap-2 ${isConnected ? "text-green-400" : "text-red-400"}`}>
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}></span>
              {isConnected ? "Live" : "Disconnected"}
            </span>
            <span className="text-xs text-gray-500">{WS_URL}</span>
            <button
              onClick={toggleMute}
              className={`text-xs px-3 py-1 rounded border transition-colors ${
                isMuted ? "border-red-700 text-red-400 hover:border-red-500" : "border-gray-600 text-gray-300 hover:border-gray-400"
              }`}
            >
              {isMuted ? "Unmute" : "Mute"}
            </button>
          </div>
        </div>

        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Spectrum Analyzer</TabsTrigger>
            <TabsTrigger value="tab2">Packet Stream</TabsTrigger>
            <TabsTrigger value="tab3">Settings</TabsTrigger>
            <TabsTrigger value="tab4">Rules</TabsTrigger>
          </TabsList>

          <TabsContent value="tab1">
            {/* You would typically place your PacketTable and SpectrumAnalyzer side-by-side here */}
            <SpectrumAnalyzer spectrumRef={latestSpectrumRef} annotationsRef={latestAnnotationsRef} />
          </TabsContent>

          <TabsContent value="tab2">
            <PacketStream />
          </TabsContent>

          <TabsContent value="tab3">{/* ... Settings content remains exactly the same ... */}</TabsContent>

          <TabsContent value="tab4">
            <RulesTab />
          </TabsContent>
        </Tabs>
      </section>
    </>
  );
}

export default App;
