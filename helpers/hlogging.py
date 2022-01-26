"""
Import as:

import helpers.hlogging as hloggin
"""

import asyncio
import copy
import datetime
import logging
from typing import Any, Iterable, List, Optional, Tuple, Union

# Avoid dependency from other helpers modules since this is used when the code
# is bootstrapped.


_LOG = logging.getLogger(__name__)


# #############################################################################


# Copied from `helpers/hsystem.py` to avoid circular imports.
def _is_running_in_ipynb() -> bool:
    try:
        _ = get_ipython().config  # type: ignore
        res = True
    except NameError:
        res = False
    return res


# Copied from `helpers/hsystem.py` to avoid circular dependencies.
def get_user_name() -> str:
    import getpass

    res = getpass.getuser()
    return res


def get_memory_usage(process: Optional[Any] = None) -> Tuple[float, float, float]:
    """
    Return the memory usage in terms of resident, virtual, and percent of total
    used memory.
    """
    if process is None:
        import psutil

        process = psutil.Process()
    rss_in_GB = process.memory_info().rss / (1024 ** 3)
    vms_in_GB = process.memory_info().vms / (1024 ** 3)
    mem_pct = process.memory_percent()
    return (rss_in_GB, vms_in_GB, mem_pct)


def get_memory_usage_as_str(process: Optional[Any] = None) -> str:
    """
    Like `get_memory_usage()` but returning a formatted string.
    """
    (rss_in_GB, vms_in_GB, mem_pct) = get_memory_usage(process)
    resource_use = "rss=%.3fGB vms=%.3fGB mem_pct=%.0f%%" % (
        rss_in_GB,
        vms_in_GB,
        mem_pct,
    )
    return resource_use


# #############################################################################
# Utils.
# #############################################################################


def reset_logger() -> None:
    import importlib

    print("Resetting logger...")
    logging.shutdown()
    importlib.reload(logging)


def get_all_loggers() -> List:
    """
    Return list of all registered loggers.
    """
    logger_dict = logging.root.manager.loggerDict  # type: ignore  # pylint: disable=no-member
    loggers = [logging.getLogger(name) for name in logger_dict]
    return loggers


def get_matching_loggers(
    module_names: Union[str, Iterable[str]], verbose: bool
) -> List:
    """
    Find loggers that match a name or a name in a set.
    """
    if isinstance(module_names, str):
        module_names = [module_names]
    loggers = get_all_loggers()
    if verbose:
        print("loggers=\n", "\n".join(map(str, loggers)))
    #
    sel_loggers = []
    for module_name in module_names:
        if verbose:
            print("module_name=%s" % module_name)
        # TODO(gp): We should have a regex.
        # str(logger) looks like `<Logger tornado.application (DEBUG)>`
        sel_loggers_tmp = [
            logger
            for logger in loggers
            if str(logger).startswith("<Logger " + module_name)
            # logger for logger in loggers if module_name in str(logger)
        ]
        # print(sel_loggers_tmp)
        sel_loggers.extend(sel_loggers_tmp)
    if verbose:
        print("sel_loggers=%s" % sel_loggers)
    return sel_loggers


def shutup_chatty_modules(
    verbosity: int = logging.CRITICAL, verbose: bool = False
) -> None:
    """
    Reduce the verbosity for external modules that are very chatty.

    :param verbosity: level of verbosity used for chatty modules: the higher the
        better
    :param verbose: print extra information
    """
    module_names = [
        "aiobotocore",
        "asyncio",
        "boto",
        "boto3",
        "botocore",
        "fsspec",
        "hooks",
        # "ib_insync",
        "invoke",
        "matplotlib",
        "nose",
        "s3fs",
        "s3transfer",
        "urllib3",
    ]
    loggers = get_matching_loggers(module_names, verbose)
    loggers = sorted(loggers, key=lambda logger: logger.name)
    for logger in loggers:
        logger.setLevel(verbosity)
    if len(loggers) > 0:
        _LOG.debug(
            "Shut up %d modules: %s",
            len(loggers),
            ", ".join([logger.name for logger in loggers]),
        )
        # if _LOG.getEffectiveLevel() < logging.DEBUG:
        #    print(WARNING +
        #       " Shutting up %d modules: %s"
        #       % (len(loggers), ", ".join([logger.name for logger in loggers]))
        #    )


def test_logger() -> None:
    print("# Testing logger ...")
    _log = logging.getLogger(__name__)
    print("effective level=", _log.getEffectiveLevel())
    #
    _log.debug("DEBUG=%s", logging.DEBUG)
    #
    _log.info("INFO=%s", logging.INFO)
    #
    _log.warning("WARNING=%s", logging.WARNING)
    #
    _log.critical("CRITICAL=%s", logging.CRITICAL)


# #############################################################################
# Logging formatter v1
# #############################################################################


# From https://stackoverflow.com/questions/32402502
class _LocalTimeZoneFormatter:
    """
    Override logging.Formatter to use an aware datetime object.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        try:
            # TODO(gp): Automatically detect the time zone. It might be complicated in
            #  Docker.
            from dateutil import tz

            # self._tzinfo = pytz.timezone('America/New_York')
            self._tzinfo = tz.gettz("America/New_York")
        except ModuleNotFoundError as e:
            print("Can't import dateutil: using UTC\n%s" % str(e))
            self._tzinfo = None

    def converter(self, timestamp: float) -> datetime.datetime:
        # To make the linter happy and respecting the signature of the
        # superclass method.
        _ = self
        # timestamp=1622423570.0147252
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        # Convert it to an aware datetime object in UTC time.
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        if self._tzinfo is not None:
            # Convert it to desired timezone.
            dt = dt.astimezone(self._tzinfo)
        return dt

    def formatTime(
        self, record: logging.LogRecord, datefmt: Optional[str] = None
    ) -> str:
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            try:
                s = dt.isoformat(timespec="milliseconds")
            except TypeError:
                s = dt.isoformat()
        return s


# #############################################################################


# [mypy] error: Definition of "converter" in base class
# "_LocalTimeZoneFormatter" is incompatible with definition in base class
# "Formatter"
class _ColoredFormatter(  # type: ignore[misc]
    _LocalTimeZoneFormatter, logging.Formatter
):
    """
    Logging formatter using colors for different levels.
    """

    _SKIP_DEBUG = True

    MAPPING = {
        # White: 37.
        # Blu.
        "DEBUG": (34, "DEBUG"),
        # Cyan.
        "INFO": (36, "INFO "),
        # Yellow.
        "WARNING": (33, "WARN "),
        # Red.
        "ERROR": (31, "ERROR"),
        # White on red background.
        "CRITICAL": (41, "CRTCL"),
    }

    def format(self, record: logging.LogRecord) -> str:
        colored_record = copy.copy(record)
        # `levelname` is the internal name and can't be changed to `level_name`
        # as per our conventions.
        levelname = colored_record.levelname
        if _ColoredFormatter._SKIP_DEBUG and levelname == "DEBUG":
            colored_levelname = ""
        else:
            # Use white as default.
            prefix = "\033["
            suffix = "\033[0m"
            assert levelname in self.MAPPING, "Can't find info '%s'"
            color_code, tag = self.MAPPING[levelname]
            # Align the level name.
            colored_levelname = "{0}{1}m{2}{3}".format(
                prefix, color_code, tag, suffix
            )
        colored_record.levelname = colored_levelname
        return logging.Formatter.format(self, colored_record)


# #############################################################################


# From https://stackoverflow.com/questions/10848342
# and https://docs.python.org/3/howto/logging-cookbook.html#filters-contextual
class ResourceUsageFilter(logging.Filter):
    """
    Add fields to the logger about memory and CPU use.
    """

    def __init__(self, report_cpu_usage: bool):
        super().__init__()
        import psutil

        self._process = psutil.Process()
        self._report_cpu_usage = report_cpu_usage
        if self._report_cpu_usage:
            # Start sampling the CPU usage.
            self._process.cpu_percent(interval=1.0)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Override `logging.Filter()`, adding several fields to the logger.
        """
        p = self._process
        # Report memory usage.
        resource_use = get_memory_usage_as_str(p)
        # Report CPU usage.
        if self._report_cpu_usage:
            # CPU usage since the previous call.
            cpu_use = p.cpu_percent(interval=None)
            resource_use += " cpu=%.0f%%" % cpu_use
        record.resource_use = resource_use  # type: ignore
        return True


# #############################################################################


# TODO(gp): Replace `force_print_format` and `force_verbose_format` with `mode`.
def _get_logging_format(
    force_print_format: bool,
    force_verbose_format: bool,
    force_no_warning: bool,
    report_memory_usage: bool,
    date_format_mode: str = "time",
) -> Tuple[str, str]:
    """
    Compute the logging format depending whether running on notebook or in a
    shell.

    The logging format can be:
    - print: looks like a `print` statement

    :param force_print_form: force to use the non-verbose format
    :param force_verbose_format: force to use the verbose format
    """
    if _is_running_in_ipynb() and not force_no_warning:
        print(WARNING + ": Running in Jupyter")
    verbose_format = not _is_running_in_ipynb()
    #
    assert not (force_verbose_format and force_print_format), (
        f"Can't use both force_verbose_format={force_verbose_format} "
        + f"and force_print_format={force_print_format}"
    )
    if force_verbose_format:
        verbose_format = True
    if force_print_format:
        verbose_format = False
        #
    if verbose_format:
        # TODO(gp): We would like to have filename:name:funcName:lineno all
        #  justified on 15 chars.
        #  See https://docs.python.org/3/howto/logging-cookbook.html#use-of
        #  -alternative-formatting-styles
        #  Something like:
        #   {{asctime}-5s {{filename}{name}{funcname}{linedo}d}-15s {message}
        #
        # %(pathname)s Full pathname of the source file where the logging call was
        #   issued (if available).
        # %(filename)s Filename portion of pathname.
        # %(module)s Module (name portion of filename).
        if True:
            log_format = (
                # 04-28_08:08 INFO :
                "%(asctime)-5s %(levelname)-5s"
            )
            if report_memory_usage:
                # rss=0.3GB vms=2.0GB mem_pct=2% cpu=91%
                log_format += " [%(resource_use)-40s]"
            log_format += (
                # lib_tasks _delete_branches
                " %(module)-20s: %(funcName)-30s:"
                # 142: ...
                " %(lineno)-4d:"
                " %(message)s"
            )
        else:
            # Super verbose: to help with debugging print more info without trimming.
            log_format = (
                # 04-28_08:08 INFO :
                "%(asctime)-5s %(levelname)-5s"
                # .../src/lem1/amp/helpers/system_interaction.py
                # _system       :
                " %(pathname)s %(funcName)-20s "
                # 199: ...
                " %(lineno)d:"
                " %(message)s"
            )
        if date_format_mode == "time":
            date_fmt = "%H:%M:%S"
        elif date_format_mode == "date_time":
            date_fmt = "%m-%d_%H:%M"
        elif date_format_mode == "date_timestamp":
            date_fmt = "%Y-%m-%d %I:%M:%S %p"
        else:
            raise ValueError("Invalid date_format_mode='%s'" % date_format_mode)
    else:
        # Make logging look like a normal print().
        # TODO(gp): We want to still prefix with WARNING and ERROR.
        log_format = "%(message)s"
        date_fmt = ""
    return date_fmt, log_format


def set_v1_formatter(
    ch: Any,
    root_logger: Any,
    force_no_warning: bool,
    force_print_format: bool,
    force_verbose_format: bool,
    report_cpu_usage: bool,
    report_memory_usage: bool,
):
    # Decide whether to use verbose or print format.
    date_fmt, log_format = _get_logging_format(
        force_print_format,
        force_verbose_format,
        force_no_warning,
        report_memory_usage,
    )
    # Use normal formatter.
    # formatter = logging.Formatter(log_format, datefmt=date_fmt)
    # Use formatter with colors.
    formatter = _ColoredFormatter(log_format, date_fmt)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)
    # Report resource usage.
    if report_memory_usage:
        # Get root logger.
        log = logging.getLogger("")
        # Create filter.
        f = ResourceUsageFilter(report_cpu_usage)
        # The ugly part:adding filter to handler.
        log.handlers[0].addFilter(f)
    return formatter


# #############################################################################
# Logging formatter v2
# #############################################################################


class CustomFormatter(logging.Formatter):
    """
    Override `format` to implement a completely custom logging formatting.

    The logging output looks like:
    ```
    07:37:17 /app/amp/helpers/hunit_test.py setUp 932 - Resetting random.seed to 20000101
    ```
    or for simulated time:
    ```
    07:43:17 @ 2022-01-18 02:43:17 workload /app/amp/helpers/test/test_hlogging.py workload:33 -   -> wait
    ```
    """

    def __init__(self,
                 *args: Any,
                 date_format_mode: str = "time",
                 report_memory_usage: bool = False,
                 report_cpu_usage: bool = False,
                 **kwargs: Any):
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._date_fmt = self._get_date_format(date_format_mode)
        #
        try:
            # TODO(gp): Automatically detect the time zone. It might be complicated in
            #  Docker.
            from dateutil import tz

            self._tzinfo = tz.gettz("America/New_York")
        except ModuleNotFoundError as e:
            print("Can't import dateutil: using UTC\n%s" % str(e))
            self._tzinfo = None
        #
        self._report_memory_usage = report_memory_usage
        self._report_cpu_usage = report_cpu_usage
        if self._report_memory_usage or self._report_cpu_usage:
            import psutil

            self._process = psutil.Process()
            if self._report_cpu_usage:
                # Start sampling the CPU usage.
                self._process.cpu_percent(interval=1.0)

    def format(self, record: logging.LogRecord) -> str:
        # record = copy.copy(record)
        # print(pprint.pformat(record.__dict__))
        # `record` looks like:
        # {'args': (30,),
        #  'created': 1642456725.5569131,
        #  'exc_info': None,
        #  'exc_text': None,
        #  'filename': 'logging_main.py',
        #  'funcName': 'test_logger',
        #  'levelname': 'WARNING',
        #  'levelno': 30,
        #  'lineno': 105,
        #  'module': 'logging_main',
        #  'msecs': 556.9131374359131,
        #  'msg': 'WARNING=%s',
        #  'name': '__main__',
        #  'pathname': 'helpers/logging_testing/logging_main.py',
        #  'process': 16484,
        #  'processName': 'MainProcess',
        #  'relativeCreated': 29.956817626953125,
        #  'stack_info': None,
        #  'thread': 140250120021824,
        #  'threadName': 'MainThread'}

        msg = ""
        # Add the wall clock time.
        msg += self._get_wall_clock_time()
        # Report memory usage, if needed.
        # rss=0.240GB vms=1.407GB mem_pct=2% cpu=92%
        if self._report_memory_usage:
            msg_tmp = get_memory_usage_as_str(self._process)
            # Escape the % to avoid confusing for a string to expand.
            msg_tmp = msg_tmp.replace("%", "%%")
            msg += " " + msg_tmp
        # Report CPU usage, if needed.
        if self._report_cpu_usage:
            # CPU usage since the previous call.
            msg_tmp = " cpu=%.0f" % self._process.cpu_percent(interval=None)
            # Escape the % to avoid confusing for a string to expand.
            msg_tmp += "%%"
            msg += msg_tmp
        # Get the (typically) simulated wall clock time.
        import helpers.hwall_clock_time as hwacltim

        simulated_wall_clock_time = hwacltim.get_wall_clock_time()
        if simulated_wall_clock_time is not None:
            date_fmt = "%Y-%m-%d %I:%M:%S"
            msg += " @ " + self._convert_time_to_string(
                simulated_wall_clock_time, date_fmt
            )
        # Colorize / shorten the logging level if it's not DEBUG.
        if record.levelno != logging.DEBUG:
            msg += " - %s" % self._colorize_level(record.levelname)
        # Add information about which coroutine we are running in.
        try:
            asyncio.get_running_loop()
            task = asyncio.Task.current_task()
            if task is not None:
                msg += " %s" % task.get_name()
        except (RuntimeError, AttributeError):
            pass
        # Add information about the caller.
        # ```
        # /helpers/hunit_test.py setUp:932
        # ```
        # pathname = record.pathname.replace("/amp", "")
        # msg += " %s %s:%s" % (pathname, record.funcName, record.lineno)
        # ```
        # test_hlogging.py _print_time:28
        # ```
        msg += " %s %s:%s" % (record.filename, record.funcName, record.lineno)
        # Indent.
        if len(msg) < 50:
            msg = "%-60s" % msg
        else:
            msg = "%-80s" % msg
        # Add the caller string.
        msg += " %s" % record.msg
        record.msg = msg
        return super().format(record)

    @staticmethod
    def _get_date_format(date_format_mode: str) -> str:
        if date_format_mode == "time":
            date_fmt = "%H:%M:%S"
        elif date_format_mode == "date_time":
            date_fmt = "%m-%d_%H:%M"
        elif date_format_mode == "date_timestamp":
            date_fmt = "%Y-%m-%d %I:%M:%S %p"
        else:
            raise ValueError("Invalid date_format")
        return date_fmt

    def _convert_time_to_string(
        self, now: datetime.datetime, date_fmt: str
    ) -> str:
        # Convert it to an tz-aware datetime object in UTC time.
        dt = now.replace(tzinfo=datetime.timezone.utc)
        if self._tzinfo is not None:
            # Convert it to desired timezone.
            dt = dt.astimezone(self._tzinfo)
        time_as_str = dt.strftime(date_fmt)
        return time_as_str

    _COLOR_MAPPING = {
        # White: 37.
        # Blu.
        "DEBUG": (34, "DEBUG"),
        # Cyan.
        "INFO": (36, "INFO "),
        # Yellow.
        "WARNING": (33, "WARN "),
        # Red.
        "ERROR": (31, "ERROR"),
        # White on red background.
        "CRITICAL": (41, "CRTCL"),
    }

    def _get_wall_clock_time(self) -> str:
        dt = datetime.datetime.utcnow()
        return self._convert_time_to_string(dt, self._date_fmt)

    def _colorize_level(self, level_name: str) -> str:
        # Use white as default.
        prefix = "\033["
        suffix = "\033[0m"
        assert level_name in self._COLOR_MAPPING, "Can't find info '%s'"
        color_code, tag = self._COLOR_MAPPING[level_name]
        colored_level_name = "{0}{1}m{2}{3}".format(
            prefix, color_code, tag, suffix
        )
        return colored_level_name



def set_v2_formatter(
    ch: Any,
    root_logger: Any,
    force_no_warning: bool,
    force_print_format: bool,
    force_verbose_format: bool,
    report_memory_usage: bool,
    report_cpu_usage: bool,
):
    """
    Same params as `init_logger()`.
    """
    assert not (force_verbose_format and force_print_format), (
          f"Can't use both force_verbose_format={force_verbose_format} "
          + f"and force_print_format={force_print_format}")
    # When running in a notebook make logging behave like a `print`.
    verbose_format = True
    if _is_running_in_ipynb():
        verbose_format = False
        if not force_no_warning:
            print(WARNING + ": Running in Jupyter")
    #
    if force_verbose_format:
        verbose_format = True
    if force_print_format:
        verbose_format = False
    #
    if verbose_format:
        # Force to report memory / CPU usage.
        # report_memory_usage = report_cpu_usage = True
        formatter = CustomFormatter(
            report_memory_usage=report_memory_usage,
            report_cpu_usage=report_cpu_usage)
    else:
        # Make logging look like a normal `print()`.
        log_format = "%(levelname)-5s %(message)s"
        date_fmt = ""
        formatter = logging.Formatter(log_format, datefmt=date_fmt)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)
    return formatter