import json
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Dict, List, Union


def load_results(file_path: str) -> Union[Dict, List[Dict]]:
    """Load results from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def extract_metrics_for_plotting(results_data: Union[Dict, List[Dict]], metric_name: str) -> tuple:
    """
    Extracts x-axis labels and y-axis values for plotting a specific metric.
    Handles both batch_results.json and grid_search_results.json formats.
    """
    x_labels = []
    y_values = []

    if isinstance(results_data, list):
        for item in results_data:
            # Handle grid search results (with averaged_statistics) or batch results (with statistics)
            stats = item.get('averaged_statistics') or item.get('statistics')
            params = item.get('parameters')

            if stats and stats.get(metric_name) is not None:
                y_values.append(stats[metric_name])

                # Create a label from the parameters, focusing on key resource counts
                label_parts = []
                if 'resources' in params:
                    for res_name, count in params['resources'].items():
                        label_parts.append(f"{res_name}:{count}")
                if 'passenger_arrival_rate' in params:
                    label_parts.append(f"arr_rate:{params['passenger_arrival_rate']}")
                if 'max_time' in params:
                    label_parts.append(f"max_time:{params['max_time']}")

                x_labels.append(", ".join(label_parts))
    return x_labels, y_values


def plot_metric(results_file: str, metric: str, title: str = None, save_path: str = None):
    """Plot a specific metric from the results file."""
    data = load_results(results_file)
    x_labels, y_values = extract_metrics_for_plotting(data, metric)

    if not x_labels or not y_values:
        print(f"No data found for metric '{metric}' in file '{results_file}'.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(range(len(x_labels)), y_values, tick_label=x_labels)
    ax.set_xlabel('Configuration')
    ax.set_ylabel(metric.replace('_', ' ').title())
    ax.set_title(title or f'Plot of {metric.replace("_", " ").title()}')
    ax.tick_params(axis='x', rotation=45, labelsize=8)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()


def plot_comparison(results_file_1: str, results_file_2: str, metric: str, label_1: str = "Results 1",
                    label_2: str = "Results 2"):
    """Compare a specific metric between two result files."""
    data1 = load_results(results_file_1)
    data2 = load_results(results_file_2)

    x_labels1, y_values1 = extract_metrics_for_plotting(data1, metric)
    x_labels2, y_values2 = extract_metrics_for_plotting(data2, metric)

    # For comparison, we assume the x-axis represents the same configurations or can be aligned
    # This is a simple approach plotting both series with potentially different x-axes
    fig, ax = plt.subplots(figsize=(12, 6))

    x1 = range(len(y_values1))
    x2 = range(len(y_values2))

    ax.plot(x1, y_values1, marker='o', label=label_1, linestyle='-', linewidth=2)
    ax.plot(x2, y_values2, marker='s', label=label_2, linestyle='-', linewidth=2)

    ax.set_xlabel('Experiment / Configuration Index')
    ax.set_ylabel(metric.replace('_', ' ').title())
    ax.set_title(f'Comparison of {metric.replace("_", " ").title()}')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.show()


def plot_resource_utilization(results_file: str, save_path: str = None):
    """Plot resource utilization for a single result set."""
    data = load_results(results_file)

    # Assuming we take the first result if it's a list (e.g., from batch or grid search)
    stats = None
    if isinstance(data, list) and len(data) > 0:
        first_result = data[0]
        stats = first_result.get('averaged_statistics') or first_result.get('statistics')
    elif isinstance(data, dict):
        stats = data.get('statistics')  # For a single result dict

    if not stats or 'utilization' not in stats:
        print("No utilization data found in the results file.")
        return

    util_data = stats['utilization']
    resources = list(util_data.keys())
    util_values = [util_data[res] for res in resources]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(resources, util_values, color='skyblue', edgecolor='navy', linewidth=0.7)
    ax.set_xlabel('Resource')
    ax.set_ylabel('Utilization Rate')
    ax.set_title('Resource Utilization Rates')
    ax.set_ylim(0, 1)  # Utilization is a percentage between 0 and 1
    ax.tick_params(axis='x', rotation=45)

    # Add value labels on bars
    for bar, value in zip(bars, util_values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height + 0.01,
                f'{value:.2%}',
                ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()


def plot_throughput_vs_wait(results_file: str, save_path: str = None):
    """Scatter plot of absolute throughput vs average wait time."""
    data = load_results(results_file)

    throughputs = []
    wait_times = []
    labels = []

    if isinstance(data, list):
        for item in data:
            stats = item.get('averaged_statistics') or item.get('statistics')
            params = item.get('parameters')
            if stats and 'absolute_throughput' in stats and 'avg_wait_time' in stats:
                throughputs.append(stats['absolute_throughput'])
                wait_times.append(stats['avg_wait_time'])
                # Use a simple label like experiment ID or a hash of params
                labels.append(
                    item.get('experiment_id', item.get('parameters', {}).get('passenger_arrival_rate', 'N/A')))

    if not throughputs or not wait_times:
        print("No throughput and wait time data found for scatter plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(wait_times, throughputs, c='coral', s=100, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Average Wait Time (minutes)')
    ax.set_ylabel('Absolute Throughput (passengers/hour)')
    ax.set_title('Throughput vs. Wait Time')
    ax.grid(True, linestyle='--', alpha=0.6)

    # Annotate points with labels (optional, can be cluttered)
    # for i, label in enumerate(labels):
    #     ax.annotate(label, (wait_times[i], throughputs[i]), textcoords="offset points", xytext=(0,10), ha='center')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()


def main():
    """Main function to demonstrate visualization options."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python visualize_results.py plot_metric <results_file.json> <metric_name> [title] [save_path]")
        print(
            "  python visualize_results.py compare <results_file_1.json> <results_file_2.json> <metric_name> [label1] [label2]")
        print("  python visualize_results.py plot_utilization <results_file.json> [save_path]")
        print("  python visualize_results.py plot_throughput_vs_wait <results_file.json> [save_path]")
        print("\nExample metrics: avg_wait_time, absolute_throughput, relative_throughput, avg_passengers_in_system")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'plot_metric':
        if len(sys.argv) < 4:
            print(
                "Usage: python visualize_results.py plot_metric <results_file.json> <metric_name> [title] [save_path]")
            sys.exit(1)
        file_path = sys.argv[2]
        metric = sys.argv[3]
        title = sys.argv[4] if len(sys.argv) > 4 else None
        save_path = sys.argv[5] if len(sys.argv) > 5 else None
        plot_metric(file_path, metric, title, save_path)

    elif command == 'compare':
        if len(sys.argv) < 5:
            print(
                "Usage: python visualize_results.py compare <results_file_1.json> <results_file_2.json> <metric_name> [label1] [label2]")
            sys.exit(1)
        file_path1 = sys.argv[2]
        file_path2 = sys.argv[3]
        metric = sys.argv[4]
        label1 = sys.argv[5] if len(sys.argv) > 5 else "Results 1"
        label2 = sys.argv[6] if len(sys.argv) > 6 else "Results 2"
        plot_comparison(file_path1, file_path2, metric, label1, label2)

    elif command == 'plot_utilization':
        if len(sys.argv) < 3:
            print("Usage: python visualize_results.py plot_utilization <results_file.json> [save_path]")
            sys.exit(1)
        file_path = sys.argv[2]
        save_path = sys.argv[3] if len(sys.argv) > 3 else None
        plot_resource_utilization(file_path, save_path)

    elif command == 'plot_throughput_vs_wait':
        if len(sys.argv) < 3:
            print("Usage: python visualize_results.py plot_throughput_vs_wait <results_file.json> [save_path]")
            sys.exit(1)
        file_path = sys.argv[2]
        save_path = sys.argv[3] if len(sys.argv) > 3 else None
        plot_throughput_vs_wait(file_path, save_path)

    else:
        print("Invalid command. Use 'plot_metric', 'compare', 'plot_utilization', or 'plot_throughput_vs_wait'.")
        sys.exit(1)


if __name__ == "__main__":
    main()