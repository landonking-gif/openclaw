import json
import glob
import os

files = glob.glob('/Users/landonking/openclaw-army/agents/*/openclaw.json')
for file in files:
    with open(file, 'r') as f:
        data = json.load(f)
    
    # Let's fix the models section
    provider_models_needed = [
        {
            "id": "meta/llama-3.3-70b-instruct",
            "name": "Llama 3.3 70B (NVIDIA)",
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 4096
        },
        {
            "id": "nvidia/llama-3.1-nemotron-70b-instruct",
            "name": "Nemotron 70B (NVIDIA)",
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 4096
        }
    ]
    
    nvidia_provider = data.get('models', {}).get('providers', {}).get('nvidia', {})
    if 'models' in nvidia_provider:
        existing_ids = set(m['id'] for m in nvidia_provider['models'])
        for m in provider_models_needed:
            if m['id'] not in existing_ids:
                nvidia_provider['models'].append(m)

    # Let's also ensure fallbacks are set correctly
    defaults = data.get('agents', {}).get('defaults', {})
    if 'model' in defaults:
        primary = defaults['model'].get('primary', '')
        # Give some robust fallbacks that definitely exist
        fallbacks = [m for m in [
            "nvidia/deepseek-ai/deepseek-r1",
            "nvidia/moonshotai/kimi-k2.5",
            "nvidia/z-ai/glm-5",
            "nvidia/meta/llama-3.3-70b-instruct"
        ] if m != primary][:2]
        defaults['model']['fallbacks'] = fallbacks

    with open(file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Fixed {file}")
