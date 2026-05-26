import numpy as np
import sklearn.metrics.pairwise as sklearn_pairwise_metrics

PAIRWISE_METRICS_MAP = {
    'cos': sklearn_pairwise_metrics.cosine_similarity,
    'dot': lambda x, y: x @ y.T,
    'l2': sklearn_pairwise_metrics.euclidean_distances,
    'l1': sklearn_pairwise_metrics.manhattan_distances,
    'lk': sklearn_pairwise_metrics.laplacian_kernel,
    'pk': sklearn_pairwise_metrics.polynomial_kernel,
    'rbfk': sklearn_pairwise_metrics.rbf_kernel,
    'sk': sklearn_pairwise_metrics.sigmoid_kernel,
    'l1min': lambda x, y: np.min(np.abs(x - y), axis=1),
    'l1max': lambda x, y: np.max(np.abs(x - y), axis=1),
}


def sanitize_metric_input(x):
    if isinstance(x, np.ndarray):
        return x
    if isinstance(x, list):
        if isinstance(x[0], list):
            return np.array(x)
        else:
            return np.reshape(np.array(x), (1, -1))
    return np.array(x)


def get_pairwise_metrics(
        X, Y,
        metric_names=None,
        flatten=False,
        unpack_single=False,
        decimals=6,
        return_list=False
):
    out = [] if return_list else {}
    if metric_names:
        metric_names = [metric_name for metric_name in metric_names if metric_name in PAIRWISE_METRICS_MAP]
    else:
        metric_names = PAIRWISE_METRICS_MAP.keys()

    if metric_names:
        X = sanitize_metric_input(X)
        Y = sanitize_metric_input(Y)
        for metric_name in metric_names:
            metric_val = PAIRWISE_METRICS_MAP[metric_name](X, Y)
            if unpack_single and not isinstance(metric_val, float) and (metric_val.shape == (1, 1) or metric_val.shape == (1,)):
                metric_val = round(float(metric_val), decimals) if decimals is not None else float(metric_val)
            elif flatten:
                metric_val = [round(float(x), decimals) for x in metric_val.flatten()] if decimals is not None else [
                    float(x) for x in metric_val.flatten()]
            elif decimals is not None:
                metric_val = np.round(metric_val, decimals=decimals)

            if return_list:
                out.append(metric_val)
            else:
                out[metric_name] = metric_val

    return out

