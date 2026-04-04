import React, { useRef, useEffect, useMemo, useCallback } from 'react';
import UplotReact from 'uplot-react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

export interface Annotation {
  label: string;
  frequency: number;
}

export interface SpectrumAnalyzerProps {
  // Accept Refs instead of raw data to bypass React re-renders!
  spectrumRef: React.MutableRefObject<number[]>;
  annotationsRef: React.MutableRefObject<Annotation[]>;
  className?: string;
}

const DEFAULT_BINS = 1024;

const generateFrequencyBins = (count: number): number[] => {
  return Array.from({ length: count }, (_, i) => i);
};

export const SpectrumAnalyzer: React.FC<SpectrumAnalyzerProps> = ({
  spectrumRef,
  annotationsRef,
  className = '',
}) => {
  const chartRef = useRef<uPlot | null>(null);
  const rafIdRef = useRef<number | null>(null);

  // 1. Draw custom annotations (Claude did this perfectly)
  const drawAnnotations = useCallback((u: uPlot) => {
    const { ctx, bbox } = u;
    const annotations = annotationsRef.current;

    if (!annotations || annotations.length === 0) return;

    ctx.save();
    ctx.font = '11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';

    annotations.forEach((annotation) => {
      const x = u.valToPos(annotation.frequency, 'x', true);
      const y = bbox.top + 10;

      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x - 4, y - 6);
      ctx.lineTo(x + 4, y - 6);
      ctx.closePath();
      ctx.fillStyle = '#f59e0b';
      ctx.fill();

      ctx.fillStyle = '#e5e7eb';
      ctx.fillText(annotation.label, x, y - 10);
    });

    ctx.restore();
  }, []);

  // 2. The true zero-render animation loop
  const drawLoop = useCallback(() => {
    if (chartRef.current && spectrumRef.current) {
      // Read data straight from the parent's ref buffer
      const xData = new Float64Array(generateFrequencyBins(spectrumRef.current.length));
      const yData = new Float64Array(spectrumRef.current);

      chartRef.current.setData([xData, yData]);
    }

    rafIdRef.current = requestAnimationFrame(drawLoop);
  }, [spectrumRef]);

  // 3. Start the loop on mount
  useEffect(() => {
    drawLoop();
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [drawLoop]);

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
      },
    },

    // Series configuration - dark mode styling
    series: [
      {}, // X-axis (placeholder)
      {
        label: 'Amplitude (dB)',
        stroke: '#3b82f6',
        width: 1.5,
        fill: 'rgba(59, 130, 246, 0.2)',
      },
    ],

    // Axes styling for dark mode
    axes: [
      {
        show: true,
        grid: {
          show: true,
          stroke: '#374151',
          width: 1,
        },
        ticks: {
          show: true,
          stroke: '#6b7280',
          width: 1,
          size: 4,
        },
        label: 'Frequency Bin',
        labelFont: 'bold 12px system-ui',
        labelColor: '#9ca3af',
        color: '#9ca3af',
        font: '11px system-ui',
        size: 50,
      },
      {
        show: true,
        grid: {
          show: true,
          stroke: '#374151',
          width: 1,
        },
        ticks: {
          show: true,
          stroke: '#6b7280',
          width: 1,
          size: 4,
        },
        label: 'Amplitude (dB)',
        labelFont: 'bold 12px system-ui',
        labelColor: '#9ca3af',
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
        stroke: '#4b5563',
        'stroke-width': 1,
      },
    },

    // Legend
    legend: {
      show: false,
    },
  }), [drawAnnotations]);

  const initialData = useMemo(() => {
    const xData = new Float64Array(generateFrequencyBins(DEFAULT_BINS));
    const yData = new Float64Array(spectrumRef.current || Array(DEFAULT_BINS).fill(-100));
    return [xData, yData];
  }, [spectrumRef]);

  return (
    <div
      className={`spectrum-analyzer ${className}`}
      style={{
        background: '#111827',
        borderRadius: '8px',
        padding: '12px',
        border: '1px solid #374151',
      }}
    >
      <UplotReact
        options={options}
        data={initialData}
        onCreate={(chart) => (chartRef.current = chart)}
        onDelete={() => (chartRef.current = null)}
      />
    </div>
  );
};

export default SpectrumAnalyzer;
