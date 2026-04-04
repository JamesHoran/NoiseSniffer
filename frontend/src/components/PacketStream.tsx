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
    <div className="p-5 bg-zinc-900/50 backdrop-blur-sm border border-zinc-700/50 rounded-xl shadow-lg">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm font-medium text-zinc-300">Packet Stream</span>
        <span className="ml-auto text-xs flex items-center gap-2 px-3 py-1 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
          <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}></span>
          <span className={isConnected ? "text-green-400" : "text-red-400"}>
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </span>
      </div>

      <table className="w-full border-collapse text-left">
        {/* 5. Header Mapping */}
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b-2 border-zinc-700/50">
              {headerGroup.headers.map((header) => (
                <th key={header.id} className="px-3 py-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>

        {/* 6. Body Mapping */}
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2 font-mono text-sm text-zinc-300">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}

          {/* Show a placeholder if no data has arrived yet */}
          {data.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-zinc-500">
                Waiting for packets...
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
