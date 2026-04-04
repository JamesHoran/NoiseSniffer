import { useState, useCallback, useRef, useEffect } from "react";
import { useReactTable, getCoreRowModel, flexRender } from "@tanstack/react-table";
// Make sure to actually import your custom useWebSocket hook!
import { useWebSocket, type PacketMessage } from "../hooks/useWebSocket";

export default function PacketStream() {
  // 1. Buffers for high-frequency data
  const latestSpectrumRef = useRef<number[]>(Array(1024).fill(-100));
  const latestAnnotationsRef = useRef<Array<{ label: string; frequency: number }>>([]);
  const packetBufferRef = useRef<PacketMessage[]>([]);

  const WS_URL = "ws://localhost:8000/ws";

  function normalizeToDb(value: number): number {
    const clamped = Math.max(0, Math.min(1, value));
    return -100 + clamped * 100;
  }

  // 2. Silently update the buffers without re-rendering React
  const handleMessage = useCallback((message: any) => {
    if (message.type === "spectrum" && message.bins) {
      latestSpectrumRef.current = message.bins.map(normalizeToDb);
      if (message.annotations) {
        latestAnnotationsRef.current = message.annotations;
      }
    } else if (message.type === "packet") {
      // Add new packet to the front, keep only the last 8
      packetBufferRef.current.unshift(message);
      if (packetBufferRef.current.length > 8) {
        packetBufferRef.current.pop();
      }
    }
  }, []);

  const { isConnected } = useWebSocket<any>(WS_URL, {
    onMessage: handleMessage,
    reconnectInterval: 3000,
    reconnectAttempts: 10,
  });

  const [data, setData] = useState<PacketMessage[]>([]);

  // 3. THE FLUSH LOOP: Periodically dump the ref buffer into React state
  useEffect(() => {
    // Update the UI twice a second (500ms). You can lower this to 250ms for a faster feel.
    const interval = setInterval(() => {
      // Only update state if there is actually data in the buffer
      if (packetBufferRef.current.length > 0) {
        // Spread into a new array so React detects the state change and re-renders
        setData([...packetBufferRef.current]);
      }
    }, 500);

    return () => clearInterval(interval); // Cleanup on unmount
  }, []);

  // 4. TanStack Column Setup
  const columns = [
    {
      accessorKey: "timestamp",
      header: "Time",
      // This intercepts the raw "2026-04-04T12:00:00.000Z" and formats it for the UI
      cell: info => {
        const rawDate = info.getValue() as string;
        const dateObj = new Date(rawDate);

        // Formats to standard local time: e.g., "12:00:00 PM"
        return dateObj.toLocaleTimeString();

        // OR, if you want high-precision 24-hour time for packet sniffing:
        // return dateObj.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 });
      },
    },
    { accessorKey: "src_ip", header: "Source" },
    { accessorKey: "dst_ip", header: "Dest" },
    { accessorKey: "protocol", header: "Protocol" },
    { accessorKey: "length", header: "Len" },
    { accessorKey: "infoString", header: "Info" },
  ];

  const table = useReactTable({
    data: data,
    columns: columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div style={{ padding: "20px", backgroundColor: "#1e1e1e", color: "#fff", borderRadius: "8px" }}>
      <div style={{ marginBottom: "10px" }}>
        <strong>Status:</strong>{" "}
        <span style={{ color: isConnected ? "#00ffcc" : "#ff4444" }}>{isConnected ? "Connected" : "Disconnected"}</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        {/* 5. Corrected Header Mapping */}
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id} style={{ borderBottom: "2px solid #444" }}>
              {headerGroup.headers.map(header => (
                <th key={header.id} style={{ padding: "8px" }}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>

        {/* 6. Corrected Body Mapping */}
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} style={{ borderBottom: "1px solid #333" }}>
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} style={{ padding: "8px", fontFamily: "monospace", fontSize: "13px" }}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}

          {/* Show a placeholder if no data has arrived yet */}
          {data.length === 0 && (
            <tr>
              <td colSpan={columns.length} style={{ padding: "15px", textAlign: "center", color: "#888" }}>
                Waiting for packets...
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
