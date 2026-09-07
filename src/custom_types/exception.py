class MyValueError(ValueError):
    def __init__(self, message: str, **context):
        self.message = message
        self.context = context
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.context:
            return self.message

        width = max(len(key) for key in self.context)

        context_str = "\n".join(
            f"    {key:<{width}} : {value}" for key, value in self.context.items()
        )

        return f"{self.message}\nContext:\n{context_str}"
