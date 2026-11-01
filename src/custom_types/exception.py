class MyValueError(ValueError):
    def __init__(self, message: str, **context):
        self.message = message
        self.context = context
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.context:
            return self.message

        indent = "    "
        context_str = "\n".join(
            f"{indent}{key}:\n"
            + "\n".join(f"{indent * 2}{line}" for line in str(value).splitlines())
            for key, value in self.context.items()
        )

        return f"{self.message}\n\nContext:\n{context_str}"
