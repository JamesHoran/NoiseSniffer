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
    // Read directly from the passed-in ref
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

  // ... (The rest of Claude's useMemo options and the return statement stay exactly the same!) ...
  
  const options = useMemo<uPlot.Options>(() => ({
    // ... Claude's uPlot styling goes here ...
    hooks: { draw: [drawAnnotations] }
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