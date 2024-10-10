def reload_pipe() -> None:
    from pipe.util import reload_pipe as _reload_pipe

    _reload_pipe()

    # wrap this in a try block because it will fail in headless mode
    try:
        import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]
        from pipe.m.usdchaser import ExportChaser

        mayaUsdLib.ExportChaser.Unregister(ExportChaser, ExportChaser.ID)
        mayaUsdLib.ExportChaser.Register(ExportChaser, ExportChaser.ID)
    except Exception:
        pass
