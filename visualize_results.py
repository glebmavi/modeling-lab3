import json
import matplotlib.pyplot as plt
import os
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
        for i, item in enumerate(results_data):
            # Handle grid search results (with averaged_statistics) or batch results (with statistics)
            stats = item.get('averaged_statistics') or item.get('statistics')
            params = item.get('parameters')

            if stats and stats.get(metric_name) is not None:
                y_values.append(stats[metric_name])

                # Create a label from the parameters, focusing on key resource counts
                label_parts = []
                if 'resources' in params:
                    # Include only a few key resources to keep label short
                    key_resources = ['registration', 'security', 'boarding']  # Adjust as needed
                    for res_name in key_resources:
                        if res_name in params['resources']:
                            label_parts.append(f"{res_name}:{params['resources'][res_name]}")
                if 'passenger_arrival_rate' in params:
                    label_parts.append(f"arr_rate:{params['passenger_arrival_rate']}")
                if 'max_time' in params:
                    label_parts.append(f"max_time:{params['max_time']}")

                # x_labels.append(f", ".join(label_parts))
                x_labels.append(f"Conf_{i+1}")
    return x_labels, y_values


def plot_metric(results_data: Union[Dict, List[Dict]], metric: str, title: str = None, save_path: str = None):
    """Plot a specific metric from the results data."""
    x_labels, y_values = extract_metrics_for_plotting(results_data, metric)

    if not x_labels or not y_values:
        print(f"No data found for metric '{metric}'. Skipping plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(range(len(x_labels)), y_values, tick_label=x_labels, color='steelblue', edgecolor='navy', linewidth=0.5)
    ax.set_xlabel('Конфигурация')
    ax.set_ylabel(metric.replace('_', ' ').title())
    ax.set_title(title or f'Plot of {metric.replace("_", " ").title()}')
    ax.bar_label(bars)
    ax.tick_params(axis='x', labelsize=7)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()


def plot_resource_utilization(results_data: Union[Dict, List[Dict]], diff_parameter: str, save_path: str = None):
    """
    Plot resource utilization for all result sets in the data.
    Each result set is shown as a group of bars (one per resource).
    """
    # Normalize input to always be a list
    if isinstance(results_data, dict):
        results_data = [results_data]

    if not results_data:
        print("No results data provided. Skipping plot.")
        return

    # Extract utilization data from each result
    all_util_data = []
    labels = []

    for i, result in enumerate(results_data):
        stats = result.get('averaged_statistics') or result.get('statistics')
        if not stats or 'utilization' not in stats:
            print(f"Skipping result {i+1}: no utilization data found.")
            continue

        util = stats['utilization']
        all_util_data.append(util)
        # Create a label based on parameters if available (e.g., arrival rate)
        arrival_rate = result.get('parameters', {}).get(diff_parameter, f"Config {i+1}")
        labels.append(f"{arrival_rate}")

    if not all_util_data:
        print("No valid utilization data found in any result. Skipping plot.")
        return

    # Ensure all util dicts have the same keys (resources)
    resources = list(all_util_data[0].keys())
    for util in all_util_data:
        if set(util.keys()) != set(resources):
            raise ValueError("All results must have the same set of resources for consistent plotting.")

    # Prepare data for plotting
    n_results = len(all_util_data)
    n_resources = len(resources)
    x = range(n_resources)
    width = 0.8 / n_results  # Total width < 0.8 to leave space between groups

    fig, ax = plt.subplots(figsize=(12, 7))

    for i, util in enumerate(all_util_data):
        util_values = [util[res] for res in resources]
        offset = (i - n_results / 2) * width + width / 2
        bars = ax.bar([xi + offset for xi in x], util_values, width=width, label=labels[i])

        # Add value labels on top of bars
        for bar, value in zip(bars, util_values):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.01,
                f'{value:.0%}',
                ha='center', va='bottom', fontsize=8
            )

    ax.set_xlabel('Ресурс')
    ax.set_ylabel('Использование ресурса')
    ax.set_title('Относительное использование ресурсов по разным сценариям')
    ax.set_ylim(0, 1.1)
    ax.set_xticks(x)
    ax.set_xticklabels(resources, rotation=45, ha='right')
    ax.legend(title="Сценарии")
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()


def plot_throughput_vs_wait(results_data: Union[Dict, List[Dict]], save_path: str = None):
    """Scatter plot of absolute throughput vs average wait time."""
    throughputs = []
    wait_times = []
    labels = []

    if isinstance(results_data, list):
        for i, item in enumerate(results_data):
            stats = item.get('averaged_statistics') or item.get('statistics')
            if stats and 'absolute_throughput' in stats and 'avg_wait_time' in stats:
                throughputs.append(stats['absolute_throughput'])
                wait_times.append(stats['avg_wait_time'])
                labels.append(f"Conf_{i + 1}")

    if not throughputs or not wait_times:
        print("No throughput and wait time data found for scatter plot. Skipping.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(wait_times, throughputs, c='mediumseagreen', s=100, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Среднее ожидание (минуты)')
    ax.set_ylabel('Абсолютная пропускная способность (пасс/час)')
    ax.set_title('Пропускная способность и Ожидание')
    ax.grid(True, alpha=0.3)

    for i, label in enumerate(labels):
        ax.annotate(label, (wait_times[i], throughputs[i]), fontsize=8,
                    textcoords="offset points", xytext=(0,10), ha='center')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    plt.show()

def list_all_configs(results_data: Union[Dict, List[Dict]]):
    configs = []

    if isinstance(results_data, list):
        for i, item in enumerate(results_data):
            configs.append(f"Config {i+1}: {json.dumps(item['parameters'])}")

    for conf in configs:
        print(conf)


def plot_all_visualizations(results_file_path: str):
    """Generate all visualizations for the given results file."""
    print(f"Loading results from {results_file_path}...")
    data = load_results(results_file_path)

    # Determine base filename for saving plots
    base_name = os.path.splitext(os.path.basename(results_file_path))[0]
    output_dir = os.path.dirname(results_file_path) or "."

    print("Generating Average Wait Time plot...")
    plot_metric(data, 'avg_wait_time',
                title=f'Среднее ожидание на конфигурацию',
                save_path=os.path.join(output_dir, f"{base_name}_avg_wait_time.png"))

    print("Generating Absolute Throughput plot...")
    plot_metric(data, 'absolute_throughput',
                title=f'Абсолютная пропускная способность на конфигурацию',
                save_path=os.path.join(output_dir, f"{base_name}_absolute_throughput.png"))

    print("Generating Relative Throughput plot...")
    plot_metric(data, 'relative_throughput',
                title=f'Относительная пропускная способность на конфигурацию',
                save_path=os.path.join(output_dir, f"{base_name}_relative_throughput.png"))

    print("Generating Average Passengers in System plot...")
    plot_metric(data, 'avg_passengers_in_system',
                title=f'Среднее число пассажиров в системе на конфигурацию',
                save_path=os.path.join(output_dir, f"{base_name}_avg_passengers_in_system.png"))

    print("Generating Generated Passengers plot...")
    plot_metric(data, 'generated_passengers',
                title='Общее количество сгенерированных пассажиров по конфигурациям',
                save_path=os.path.join(output_dir, f"{base_name}_generated_passengers.png"))

    print("Generating Served Ratio plot...")
    plot_metric(data, 'served_ratio',
                title='Доля обслуженных пассажиров (served / generated)',
                save_path=os.path.join(output_dir, f"{base_name}_served_ratio.png"))

    print("Generating Resource Utilization plot...")
    plot_resource_utilization(data,  diff_parameter='',
                              save_path=os.path.join(output_dir, f"{base_name}_utilization.png"))

    print("Generating Throughput vs. Wait Time scatter plot...")
    plot_throughput_vs_wait(data,
                            save_path=os.path.join(output_dir, f"{base_name}_throughput_vs_wait.png"))

    list_all_configs(data)

    print("\nAll visualizations have been generated and saved.")


def main():
    """Main function to run all visualizations."""
    import sys

    if len(sys.argv) != 2:
        print("Usage:")
        print("  python visualize_results.py <results_file.json>")
        print("\nThis script will generate all relevant visualizations for the provided results file.")
        sys.exit(1)

    results_file_path = sys.argv[1]

    if not os.path.exists(results_file_path):
        print(f"Error: File '{results_file_path}' not found.")
        sys.exit(1)

    plot_all_visualizations(results_file_path)


if __name__ == "__main__":
    main()