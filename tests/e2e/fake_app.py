"""The Riemann app with an instant FakeSummariser, for the browser tests
(tests/e2e). Never calls a model."""
import riemann.server as server
from riemann.abstraction.summarise import FakeSummariser

server.get_summariser = lambda model=None: FakeSummariser()
app = server.app
