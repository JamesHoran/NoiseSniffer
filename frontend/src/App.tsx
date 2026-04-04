import { useRef, useCallback } from "react";
import "./App.css";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { SpectrumAnalyzer } from "./components/SpectrumAnalyzer";
// Assuming you have a PacketTable component for the left side of your sketch
// import { PacketTable } from "./components/PacketTable";
import { useWebSocket } from "./hooks/useWebSocket";
import type { SpectrumMessage, PacketMessage } from "./hooks/useWebSocket";

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
    } 
    else if (message.type === "packet") {
      // Add new packet to the front, and keep only the last 100 to prevent memory leaks
      packetBufferRef.current.unshift(message);
      if (packetBufferRef.current.length > 100) {
        packetBufferRef.current.pop();
      }
    }
  }, []);

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
            <span className={`text-sm font-medium flex items-center gap-2 ${
              isConnected ? "text-green-400" : "text-red-400"
            }`}>
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}></span>
              {isConnected ? "Live" : "Disconnected"}
            </span>
            <span className="text-xs text-gray-500">
              {WS_URL}
            </span>
          </div>
        </div>

        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Spectrum Analyzer</TabsTrigger>
            <TabsTrigger value="tab2">Settings</TabsTrigger>
          </TabsList>
          
          <TabsContent value="tab1">
             {/* You would typically place your PacketTable and SpectrumAnalyzer side-by-side here */}
            <SpectrumAnalyzer
              spectrumRef={latestSpectrumRef}
              annotationsRef={latestAnnotationsRef}
            />
          </TabsContent>

          <TabsContent value="tab2">
             {/* ... Settings content remains exactly the same ... */}
          </TabsContent>
        </Tabs>
      </section>
    </>
  );
}

export default App;