export const metadata = { title: "Custom Models — gptcgt Docs" };

export default function DocsCustomModels() {
    return (
        <>
            <h1>Custom &amp; Local Models</h1>
            <p>gptcgt is not locked to commercial providers. You can add your own local Ollama endpoints, vLLM instances, or any OpenAI-compatible API — including models from OpenRouter&apos;s marketplace of 200+ models.</p>

            <h2>OpenRouter Integration</h2>
            <p>The easiest way to access a wide variety of models is through <strong>OpenRouter</strong>. With a single API key, you get access to hundreds of models from every major provider.</p>
            <ol>
                <li>Get an API key from <a href="https://openrouter.ai" target="_blank" rel="noopener noreferrer">openrouter.ai</a></li>
                <li>Add it in the onboarding wizard or settings</li>
                <li>gptcgt automatically fetches the latest available models from OpenRouter&apos;s API</li>
                <li>Enable specific models in your settings under <code>openrouter_active_models</code></li>
            </ol>

            <h2>Custom Model Definitions</h2>
            <p>Add custom models to your global config:</p>
            <pre><code>{`# ~/.gptcgt/global.toml

[[custom_models]]
id = "custom/llama-3-70b"
name = "Local LLaMA 3 70B"
provider = "custom"
context_window = 8192
input_price_per_1k = 0.0    # Free if running locally
output_price_per_1k = 0.0
quality_tier = "standard"
supported_features = ["tools", "streaming"]`}</code></pre>

            <h2>Connecting to Ollama</h2>
            <p>If you&apos;re running <a href="https://ollama.com" target="_blank" rel="noopener noreferrer">Ollama</a> locally:</p>
            <ol>
                <li>Start Ollama: <code>ollama serve</code></li>
                <li>Pull a model: <code>ollama pull llama3</code></li>
                <li>Add the custom model config above with <code>provider = &quot;custom&quot;</code></li>
                <li>Set the base URL environment variable:
                    <pre><code>{`export CUSTOM_API_BASE=http://localhost:11434`}</code></pre>
                </li>
            </ol>
            <p>The <code>CustomAgent</code> class routes requests through the same LiteLLM client, so all features (streaming, tool calls, token counting) work seamlessly.</p>

            <h2>vLLM &amp; Other OpenAI-Compatible Servers</h2>
            <p>Any server that implements the OpenAI Chat Completions API format works:</p>
            <pre><code>{`# Example for a vLLM server
export CUSTOM_API_BASE=http://your-gpu-server:8000/v1`}</code></pre>
            <p>Set the model ID in your custom definition to match the model name your server expects.</p>

            <h2>Model Registry</h2>
            <p>gptcgt maintains a <strong>ModelRegistry</strong> that catalogs all available models. On startup, it:</p>
            <ol>
                <li>Loads bundled model definitions from <code>src/data/models.json</code></li>
                <li>Loads your custom models from <code>~/.gptcgt/global.toml</code></li>
                <li>Fetches live pricing from LiteLLM&apos;s pricing database (1.5s timeout)</li>
                <li>If you have an OpenRouter key, fetches available models from their API</li>
            </ol>
            <p>Models are searchable by ID, provider, quality tier, and capability. The router considers all registered models when selecting the best one for your task.</p>

            <h2>Quality Tiers</h2>
            <p>Every model is assigned a quality tier that determines when it gets selected:</p>
            <ul>
                <li><strong>budget</strong> — Fast and cheap (GPT-3.5, Gemini Flash)</li>
                <li><strong>standard</strong> — Good balance of quality and cost (GPT-4o mini, Claude 3.5 Haiku)</li>
                <li><strong>max</strong> — Best available quality (Claude 3.5 Sonnet, GPT-4o, Gemini 2.5 Pro)</li>
            </ul>
            <p>Custom models default to <code>standard</code> tier unless you specify otherwise.</p>
        </>
    );
}
