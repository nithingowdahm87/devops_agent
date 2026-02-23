import concurrent.futures
from tenacity import retry, stop_after_attempt, wait_exponential

class Sampler:
    def __init__(self, llm_client, temperatures=[0.2, 1.0]):
        self.llm = llm_client
        self.temperatures = temperatures

    def _generate_candidate(self, prompt: str, temp: float) -> str:
        # Override temperature for this specific call if the client supports it
        original_temp = getattr(self.llm, 'temperature', None)
        if original_temp is not None:
            self.llm.temperature = temp
            
        try:
            print(f"  [>] Generating candidate at temp {temp}...")
            response = self.llm.call(prompt)
            return response
        except Exception as e:
            print(f"  [!] Failed to generate candidate at temp {temp}: {e}")
            return ""
        finally:
            if original_temp is not None:
                 self.llm.temperature = original_temp

    def sample(self, prompt: str) -> list[str]:
        candidates = []
        for t in self.temperatures:
            res = self._generate_candidate(prompt, t)
            if res.strip():
                candidates.append(res)
                    
        return candidates
