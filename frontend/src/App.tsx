import "./App.css";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { SpectrumAnalyzer } from "./components/SpectrumAnalyzer";

// Demo data for spectrum analyzer
const demoWave = Array.from({ length: 1024 }, () => -60 + Math.random() * 40);

const demoAnnotations = [
  { label: "ARP", frequency: 100 },
  { label: "DNS", frequency: 300 },
  { label: "HTTPS", frequency: 443 },
];

function App() {
  return (
    <>
      <section id="center">
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Spectrum Analyzer</TabsTrigger>
            <TabsTrigger value="tab2">Settings</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">
            <SpectrumAnalyzer
              data={{ wave: demoWave }}
              annotations={demoAnnotations}
            />
          </TabsContent>
          <TabsContent value="tab2">
            <div className="p-4">
              <h2 className="text-xl font-bold mb-4">Settings</h2>
              <p className="text-gray-400">Configure your spectrum analyzer settings here.</p>
            </div>
          </TabsContent>
        </Tabs>
      </section>
    </>
  );
}

export default App;
