import { useState, useCallback, useRef, useEffect } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import { useWebSocket, type PacketMessage, type WebSocketMessage } from "../hooks/useWebSocket";

export default function PacketStream() {
  // 1. Buffers for high-frequency data
  const packetBufferRef = useRef<PacketMessage[]>([]);

  const WS_URL = "ws://localhost:8000/ws";

  // 2. Silently update the buffers without re-rendering React
  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === "packet") {
      // Add new packet to the front, keep only the last 8
      packetBufferRef.current.unshift(message);
      if (packetBufferRef.current.length > 8) {
        packetBufferRef.current.pop();
      }
    }
  }, []);

  const { isConnected } = useWebSocket<WebSocketMessage>(WS_URL, {
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
  const columns: ColumnDef<PacketMessage>[] = [
    {
      accessorKey: "timestamp",
      header: "Time",
      cell: (props) => {
        const rawDate = props.getValue() as string;
        const dateObj = new Date(rawDate);
        return dateObj.toLocaleTimeString();
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
        <span style={{ color: isConnected ? "#00ffcc" : "#ff4444" }}>
          {isConnected ? "Connected" : "Disconnected"}
        </span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        {/* 5. Header Mapping */}
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} style={{ borderBottom: "2px solid #444" }}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} style={{ padding: "8px" }}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>

        {/* 6. Body Mapping */}
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} style={{ borderBottom: "1px solid #333" }}>
              {row.getVisibleCells().map((cell) => (
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
