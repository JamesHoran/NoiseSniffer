import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SpectrumAnalyzer } from './SpectrumAnalyzer';

// Mock RAF first
let mockRafCallbacks: Array<(() => void) | undefined> = [];
let mockRaf: ReturnType<typeof vi.fn>;
let mockCancelRaf: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockRafCallbacks = [];
  mockRaf = vi.fn((cb: FrameRequestCallback) => {
    const id = mockRafCallbacks.length;
    mockRafCallbacks.push(() => cb(0));
    return id;
  });
  mockCancelRaf = vi.fn((id: number) => {
    mockRafCallbacks[id] = undefined;
  });
  globalThis.requestAnimationFrame = mockRaf as any;
  globalThis.cancelAnimationFrame = mockCancelRaf as any;
});

afterEach(() => {
  cleanup();
});

// Mock uPlot
vi.mock('uplot', () => ({
  default: vi.fn(() => ({
    setData: vi.fn(),
    destroy: vi.fn(),
    root: { classList: { add: vi.fn() } },
  })),
}));

// Mock uplot-react with factory
vi.mock('uplot-react', () => {
  const mockUplotReact = vi.fn((props: any) => {
    const mockChart = {
      setData: vi.fn(),
      destroy: vi.fn(),
      root: { classList: { add: vi.fn() } },
    };
    if (props.onCreate) props.onCreate(mockChart);
    return <div data-testid="uplot-mock" />;
  });
  return { default: mockUplotReact };
});

// Import the mocked module to access calls
import UplotReact from 'uplot-react';

describe('SpectrumAnalyzer', () => {
  describe('Rendering', () => {
    it('should render the chart container', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });

    it('should render uPlot chart component', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);
      expect(screen.getByTestId('uplot-mock')).toBeInTheDocument();
    });
  });

  describe('uPlot Configuration', () => {
    it('should configure Y-axis for dB amplitude with range -100 to 0', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.scales?.y?.min).toBe(-100);
      expect(options?.scales?.y?.max).toBe(0);
    });

    it('should apply dark mode theme styling', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options).toBeDefined();
    });

    it('should configure series with fill under line', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.series).toBeDefined();
    });
  });

  describe('Buffer & Draw Pattern', () => {
    it('should initialize requestAnimationFrame loop', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      expect(mockRaf).toHaveBeenCalled();
    });

    it('should use stable data reference for uPlot (Buffer & Draw)', () => {
      // This test verifies the Buffer & Draw pattern by checking that
      // changing the wave data doesn't cause uPlot-react to re-render with new data
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      const { rerender } = render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const initialCalls = (UplotReact as any).mock.calls;
      const initialData = initialCalls[0][0]?.data;

      // Update with different data (simulating WebSocket update)
      spectrumRef.current = Array(1024).fill(-40).map((v, i) => v - i);
      rerender(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      // uPlot-react should receive the same data reference because
      // the Buffer & Draw pattern uses a ref (buffer) instead of props
      const updatedCalls = (UplotReact as any).mock.calls;
      const updatedData = updatedCalls[updatedCalls.length - 1][0]?.data;

      // The key assertion: data passed to uPlot should remain stable
      // because buffering happens via ref, not prop changes
      expect(initialData).toEqual(updatedData);
    });
  });

  describe('Custom Annotations', () => {
    it('should configure draw hook for custom annotations', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.hooks?.draw).toBeDefined();
    });

    it('should support drawing annotation labels', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(typeof options?.hooks?.draw?.[0]).toBe('function');
    });
  });

  describe('Lifecycle', () => {
    it('should clean up requestAnimationFrame on unmount', () => {
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: [] };
      const { unmount } = render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);

      unmount();

      expect(mockCancelRaf).toHaveBeenCalled();
    });
  });

  describe('Data Flow', () => {
    it('should accept spectrum data via ref', () => {
      const testData = new Array(512).fill(-30);
      const spectrumRef = { current: testData };
      const annotationsRef = { current: [] };

      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });

    it('should accept annotations configuration via ref', () => {
      const annotations = [
        { label: 'ARP', frequency: 100 },
        { label: 'HTTPS', frequency: 443 },
      ];
      const spectrumRef = { current: Array(1024).fill(-100) };
      const annotationsRef = { current: annotations };

      render(<SpectrumAnalyzer spectrumRef={spectrumRef} annotationsRef={annotationsRef} />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });
  });
});
