import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Deepseek?

model_name = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)


device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)


prompt = "Once upon a time in a distant galaxy,"


inputs = tokenizer(prompt, return_tensors="pt").to(device)

# Generate text
outputs = model.generate(
    **inputs,
    max_new_tokens=100,  # How many new tokens to generate
    temperature=0.9,     # Higher = more creative (0.7-1.0 is good for creativity)
    top_p=0.95,          # Nucleus sampling for diversity
    do_sample=True       # Enable sampling for creative output
)


generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(generated_text)