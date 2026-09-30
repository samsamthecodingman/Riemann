"""The Riemann app with an instant FakeSummariser, for the browser tests
(tests/e2e). Never calls a model. A document containing FAILME-ONCE fails its
first build with a model error (and builds normally when retried)."""
import riemann.server as server
from riemann.abstraction.summarise import FakeSummariser, ModelError

_failed: set[str] = set()


class _Summariser(FakeSummariser):
    async def summarise(self, prompt: str, system: str) -> str:
        if "FAILME-ONCE" in prompt and "once" not in _failed:
            _failed.add("once")
            raise ModelError("The model is rate-limiting requests (too many at once or quota used up). Wait a minute and try again.")
        return await super().summarise(prompt, system)


server.get_summariser = lambda model=None: _Summariser()
app = server.app
