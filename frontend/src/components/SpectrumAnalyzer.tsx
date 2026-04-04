import React, { useRef, useEffect, useMemo, useCallback } from 'react';
import UplotReact from 'uplot-react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

// Types for component props
export interface Annotation {
  label: string;
  frequency: number;
}

export interface SpectrumData {
  wave: number[];
  annotations?: Annotation[];
}

export interface SpectrumAnalyzerProps {
  data?: SpectrumData;
  annotations?: Annotation[];
  className?: string;
}

// Default frequency bin count
const DEFAULT_BINS = 1024;

// Generate default frequency bins (X-axis)
const generateFrequencyBins = (count: number): number[] => {
  return Array.from({ length: count }, (_, i) => i);
};

// Generate initial silence data
const generateSilentData = (count: number): number[] => {
  return Array.from({ length: count }, () => -100);
};

export const SpectrumAnalyzer: React.FC<SpectrumAnalyzerProps> = ({
  data: externalData,
  annotations: externalAnnotations = [],
  className = '',
}) => {
  // Mutable buffer for incoming data (Buffer & Draw pattern)
  const dataBufferRef = useRef<number[]>(generateSilentData(DEFAULT_BINS));
  const annotationsRef = useRef<Annotation[]>(externalAnnotations);

  // uPlot instance ref for direct API access
  const chartRef = useRef<uPlot | null>(null);

  // Ref to track RAF ID for cleanup
  const rafIdRef = useRef<number | null>(null);

  // Update buffer when external data changes (without causing re-render)
  useEffect(() => {
    if (externalData?.wave) {
      dataBufferRef.current = externalData.wave;
    }
  }, [externalData?.wave]);

  // Update annotations when external annotations change
  useEffect(() => {
    annotationsRef.current = externalAnnotations;
  }, [externalAnnotations]);

  // Draw annotation labels and triangles on the canvas
  const drawAnnotations = useCallback((u: uPlot) => {
    const { ctx, bbox } = u;
    const annotations = annotationsRef.current;

    if (!annotations || annotations.length === 0) return;

    ctx.save();
    ctx.font = '11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';

    annotations.forEach((annotation) => {
      // Convert frequency bin index to canvas X position
      const x = u.valToPos(annotation.frequency, 'x', true);
      const y = bbox.top + 10; // Position near top of chart

      // Draw downward triangle pointer
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x - 4, y - 6);
      ctx.lineTo(x + 4, y - 6);
      ctx.closePath();
      ctx.fillStyle = '#f59e0b'; // Amber color for visibility
      ctx.fill();

      // Draw label above triangle
      ctx.fillStyle = '#e5e7eb'; // Light gray text
      ctx.fillText(annotation.label, x, y - 10);
    });

    ctx.restore();
  }, []);

  // Buffer & Draw: Use requestAnimationFrame to update chart
  // This prevents excessive redraws from rapid WebSocket updates
  const drawLoop = useCallback(() => {
    if (chartRef.current) {
      // Create the data array for uPlot: [x-axis, y-axis series]
      // Must use TypedArrays for uPlot setData
      const xData = new Float64Array(generateFrequencyBins(dataBufferRef.current.length));
      const yData = new Float64Array(dataBufferRef.current);

      // Update uPlot data
      chartRef.current.setData([xData, yData]);
    }

    // Schedule next frame
    // eslint-disable-next-line react-hooks/immutability -- requestAnimationFrame requires self-reference
    rafIdRef.current = requestAnimationFrame(drawLoop);
  }, []);

  // Set up draw loop on mount
  useEffect(() => {
    drawLoop();

    return () => {
      // Cleanup: Cancel RAF on unmount
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [drawLoop]);

  // Memoize uPlot options to avoid recreating on every render
  const options = useMemo<uPlot.Options>(() => ({
    width: 800,
    height: 400,

    // Axes configuration
    scales: {
      x: {
        time: false,
        auto: false,
        range: [0, DEFAULT_BINS - 1],
      },
      y: {
        min: -100,
        max: 0,
        // Linear scale for dB values
      },
    },

    // Series configuration - dark mode styling
    series: [
      {}, // X-axis (placeholder)
      {
        label: 'Amplitude (dB)',
        stroke: '#3b82f6', // Blue-500
        width: 1.5,
        fill: 'rgba(59, 130, 246, 0.2)', // Semi-transparent blue fill
        // Gradient fill effect could be added with custom draw hook
      },
    ],

    // Axes styling for dark mode
    axes: [
      {
        show: true,
        grid: {
          show: true,
          stroke: '#374151', // Gray-700
          width: 1,
        },
        ticks: {
          show: true,
          stroke: '#6b7280', // Gray-500
          width: 1,
          size: 4,
        },
        label: 'Frequency Bin',
        labelFont: 'bold 12px system-ui',
        labelColor: '#9ca3af', // Gray-400
        color: '#9ca3af',
        font: '11px system-ui',
        size: 50,
      },
      {
        show: true,
        grid: {
          show: true,
          stroke: '#374151', // Gray-700
          width: 1,
        },
        ticks: {
          show: true,
          stroke: '#6b7280', // Gray-500
          width: 1,
          size: 4,
        },
        label: 'Amplitude (dB)',
        labelFont: 'bold 12px system-ui',
        labelColor: '#9ca3af', // Gray-400
        color: '#9ca3af',
        font: '11px system-ui',
        size: 60,
        values: (_self, splits) => splits.map(v => v.toFixed(0) + ' dB'),
      },
    ],

    // Hook for drawing custom annotations
    hooks: {
      draw: [
        drawAnnotations,
      ],
    },

    // Padding for labels
    padding: [null, 60, null, 50],

    // Cursor configuration
    cursor: {
      show: true,
      x: true,
      y: true,
      drag: {
        setScale: false,
        setRange: false,
      },
      points: {
        show: false,
      },
      lock: false,
      focus: {
        prox: 10,
      },
    },

    // Tooltip configuration
    tooltip: {
      show: true,
      frame: {
        stroke: '#4b5563', // Gray-600
        'stroke-width': 1,
      },
    },

    // Legend
    legend: {
      show: false,
    },
  }), [drawAnnotations]);

  // Create initial data for uPlot (must be TypedArrays)
  const initialData = useMemo(() => {
    const xData = new Float64Array(generateFrequencyBins(DEFAULT_BINS));
    const yData = new Float64Array(dataBufferRef.current);
    return [xData, yData];
  }, []);

  // Handle chart creation
  const handleCreate = useCallback((chart: uPlot) => {
    chartRef.current = chart;
  }, []);

  // Handle chart deletion
  const handleDelete = useCallback(() => {
    chartRef.current = null;
  }, []);

  return (
    <div
      data-testid="spectrum-analyzer"
      className={`spectrum-analyzer ${className}`}
      style={{
        background: '#111827', // Gray-900 dark background
        borderRadius: '8px',
        padding: '12px',
        border: '1px solid #374151', // Gray-700
      }}
    >
      <UplotReact
        options={options}
        data={initialData}
        onCreate={handleCreate}
        onDelete={handleDelete}
      />
    </div>
  );
};

export default SpectrumAnalyzer;
