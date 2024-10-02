def reload_pipe() -> None:
    import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]
    from pipe.m.usdchaser import ExportChaser
    from pipe.util import reload_pipe as _reload_pipe

    _reload_pipe()
    mayaUsdLib.ExportChaser.Unregister(ExportChaser, ExportChaser.ID)
    mayaUsdLib.ExportChaser.Register(ExportChaser, ExportChaser.ID)
