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
  spectrumRef: React.RefObject<number[]>;
  annotationsRef: React.RefObject<Annotation[]>;
  className?: string;
}

const DEFAULT_BINS = 1024;
const SAMPLE_RATE = 44100;
const FFT_SIZE = 2048;
const HZ_PER_BIN = SAMPLE_RATE / FFT_SIZE;   // ≈ 21.5 Hz per bin
const MAX_FREQ_HZ = (SAMPLE_RATE / 2);        // 22050 Hz

const generateFrequencyBins = (count: number): number[] => {
  return Array.from({ length: count }, (_, i) => i * HZ_PER_BIN);
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
  }, [annotationsRef]);

  // 2. Setup draw loop in effect only (not during render)
  useEffect(() => {
    const drawLoop = () => {
      if (chartRef.current && spectrumRef.current) {
        // Read data straight from the parent's ref buffer
        const xData = new Float64Array(generateFrequencyBins(spectrumRef.current.length));
        const yData = new Float64Array(spectrumRef.current);

        chartRef.current.setData([xData, yData]);
      }

      rafIdRef.current = requestAnimationFrame(drawLoop);
    };

    drawLoop();
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [spectrumRef]);

  const options = useMemo<uPlot.Options>(() => ({
    width: 800,
    height: 400,

    // Axes configuration
    scales: {
      x: {
        time: false,
        auto: false,
        range: [0, MAX_FREQ_HZ],
      },
      y: {
        auto: false,
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
        label: 'Frequency (Hz)',
        values: (_self, splits) => splits.map(v => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v.toFixed(0)),
        labelFont: 'bold 12px system-ui',
        stroke: '#d5d5d5',
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
        stroke: '#d5d5d5',
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

  // Initialize data once - avoid accessing ref in render
  const initialData = useMemo(() => {
    const xData = new Float64Array(generateFrequencyBins(DEFAULT_BINS));
    const yData = new Float64Array(Array(DEFAULT_BINS).fill(-100));
    return [xData, yData];
  }, []);

  return (
    <div
      className={`spectrum-analyzer ${className}`}
      data-testid="spectrum-analyzer"
      style={{
        background: 'rgba(24, 24, 27, 0.5)',
        borderRadius: '12px',
        padding: '16px',
        border: '1px solid rgba(63, 63, 70, 0.5)',
        backdropFilter: 'blur(8px)',
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
