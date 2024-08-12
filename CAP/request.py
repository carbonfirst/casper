# Authors: Basundhara Chakrabarty, Shruti Jasoria

class RequestBatch:
    """Imitates a batch of requests
    """
    def __init__(self, name, load, region):
        """

        Args:
            name: Name of request, used to debug
            load: Load of the batch of requests
            region: Region assigned to complete/outsource the requests
        """
        self.name = name
        self.load = load
        self.region = region

    def __repr__(self) -> str:
        return f"RequestBatch({self.region}, load={self.load})"
