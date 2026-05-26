import random
from typing import Iterable, TypeVar, List

T = TypeVar('T')  # Generic type


def reservoir_sample(stream: Iterable[T], k: int) -> List[T]:
    """
    Performs Reservoir Sampling on an iterable data stream to select `k` items with equal probability.

    Args:
        stream (Iterable[T]): The data stream or iterable from which to sample.
        k (int): The number of samples to select.

    Returns:
        List[T]: A list of `k` randomly selected elements from the stream.

    Notes:
        - **Time Complexity**:
            - Initializing the reservoir takes **O(k)**.
            - Iterating through the stream takes **O(n)** for `n` elements.
            - Each replacement operation is **O(1)**, leading to a total **O(n)** complexity.
        - **Space Complexity**: **O(k)** (we store only `k` elements).
        - **Proof of Equal Probability**:
            1. The **first `k` elements** are always added to the reservoir.
            2. For each **subsequent element at index `i ≥ k`**, it is selected with probability **`k / (i + 1)`** (since `random.randint(0, i)` generates `i+1` possible outcomes, and `k` of them lead to replacement).
            3. **Probability Analysis**: Let’s prove any element `X_j` (where `0 ≤ j < n`) has equal probability of being in the final sample.
                - If `j < k`, it is initially added to the reservoir.
                  - **Probability it survives each replacement**:
                    \[
                    P(X_j \text{ remains}) = \prod_{i=k}^{n-1} \left(1 - \frac{1}{i+1}\right) = \frac{k}{n}
                    \]
                - If `j ≥ k`, it is selected with probability **`k / (j + 1)`**, and must remain un-replaced thereafter:
                    \[
                    P(X_j \text{ remains}) = \frac{k}{j+1} \times \prod_{i=j+1}^{n-1} \left(1 - \frac{1}{i+1}\right) = \frac{k}{n}
                    \]
                - Therefore, for all elements, the probability of being in the final reservoir is **`k / n`**, proving equal probability selection.

    Example:
        >>> result = reservoir_sample(range(100), 5)
        >>> len(result) == 5  # The result should contain exactly 5 elements
        True
        >>> all(x in range(100) for x in result)  # All selected elements should be from the input range
        True

        >>> items = ["apple", "banana", "cherry", "date"]
        >>> result = reservoir_sample(items, 2)
        >>> len(result) == 2  # Should always return 2 elements
        True
        >>> all(x in items for x in result)  # Every element should belong to the original list
        True
    """
    reservoir = []  # Reservoir to store the selected k elements

    # Fill the reservoir initially with the first k elements
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)
        else:
            # Generate a random index between 0 and i (inclusive)
            # A reservoir position is replaced with probability k/(i+1)
            j = random.randint(0, i)
            if j < k:
                reservoir[j] = item

    return reservoir