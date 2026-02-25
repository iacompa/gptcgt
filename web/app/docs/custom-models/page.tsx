export const metadata = { title: "Custom Models — gptcgt Docs" };

export default function DocsCustomModels() {
    return (
        <>
            <h1>Custom & Local Models</h1>
            <p>gptcgt is not locked into tier-1 commercial providers. You can construct agents using local Ollama endpoints or your own vLLM instances.</p>

            <h2>Editing the Registry</h2>
            <p>Models are defined in <code>src/data/models.json</code>. You can add your own model definitions here.</p>

            <pre><code>{`{
  "id": "llama-3-8b-instruct",
  "provider": "custom",
  "context_window": 8192,
  "supported_features": ["tools", "vision"]
}`}</code></pre>

            <h2>Connecting to Localhost</h2>
            <p>When the orchestrator encounters a <code>provider: &quot;custom&quot;</code> definition, it delegates routing to the <code>CustomAgent</code> class. Ensure you supply the <code>CUSTOM_API_BASE</code> variable indicating the local port (e.g., <code>http://localhost:11434</code>).</p>
        </>
    );
}
