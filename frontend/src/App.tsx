import './App.css'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './components/ui/tabs'

function App() {
  return (
    <>
      <section id="center">
        <Tabs defaultValue="tab1">
          <TabsList>              
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>                                    
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs> 
      </section>
    </>
  )
}

export default App
