from collections import defaultdict


HISTOGRAM_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def new_histogram():
    return defaultdict(
        lambda: {
            "buckets": defaultdict(int),
            "count": 0,
            "sum": 0.0,
        }
    )


def observe_histogram(histogram, labels, value: float) -> None:
    histogram[labels]["count"] += 1
    histogram[labels]["sum"] += value
    for bucket in HISTOGRAM_BUCKETS:
        if value <= bucket:
            histogram[labels]["buckets"][bucket] += 1
    histogram[labels]["buckets"]["+Inf"] += 1


def render_histogram(lines: list[str], name: str, histogram) -> None:
    for labels, values in sorted(histogram.items()):
        provider, model, status, endpoint = labels
        for bucket in (*HISTOGRAM_BUCKETS, "+Inf"):
            bucket_labels = metric_labels(
                provider,
                model,
                status,
                endpoint,
                le=str(bucket),
            )
            lines.append(
                f"{name}_bucket"
                f'{bucket_labels} {values["buckets"][bucket]}'
            )
        lines.append(
            f"{name}_count"
            f'{metric_labels(provider, model, status, endpoint)} '
            f'{values["count"]}'
        )
        lines.append(
            f"{name}_sum"
            f'{metric_labels(provider, model, status, endpoint)} '
            f'{values["sum"]}'
        )


def metric_labels(
    provider: str,
    model: str,
    status: str,
    endpoint: str,
    le: str | None = None,
) -> str:
    labels = (
        f'provider="{provider}",model="{model}",'
        f'status="{status}",endpoint="{endpoint}"'
    )
    if le is not None:
        labels = f'{labels},le="{le}"'
    return f"{{{labels}}}"
