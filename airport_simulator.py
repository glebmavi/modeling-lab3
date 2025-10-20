import simpy
import random
import statistics
import json
import itertools
from typing import List, Dict, Any


def load_params_from_json(json_file_path: str) -> Dict[str, Any]:
    with open(json_file_path, 'r', encoding='utf-8') as f:
        params = json.load(f)
    return params


def run_simulation_with_params(params: Dict[str, Any]):
    """
    Запуск симуляции с заданными параметрами.
    """
    wait_times = []
    service_stats = {
        'registration': [],
        'security': [],
        'customs': [],
        'duty_free': [],
        'restaurant': [],
        'toilet': [],
        'boarding': []
    }
    served_passengers = 0
    rejected_passengers = 0
    timeout_passengers = 0

    MAX_WAIT_TIME = params.get('max_time', 180)
    SIMULATION_TIME = params.get('simulation_time', 480)  # Default 8 hours
    INITIAL_PASSENGERS = params.get('initial_passengers', 100)

    # Resource counts
    num_registration_agents = params['resources']['registration']
    num_security_agents = params['resources']['security']
    num_customs_agents = params['resources']['customs']
    num_duty_free_cashiers = params['resources']['duty_free']
    num_restaurant_tables = params['resources']['restaurant']
    num_toilets_before = params['resources']['toilet_before']
    num_toilets_after = params['resources']['toilet_after']
    num_boarding_gates = params['resources']['boarding']

    # Probabilities
    prob_customs = params['probabilities'].get('customs', 0.7)
    prob_duty_free = params['probabilities'].get('duty_free', 0.1)
    prob_restaurant = params['probabilities'].get('restaurant', 0.33)
    prob_toilet_before = params['probabilities'].get('toilet_before', 0.2)
    prob_toilet_after = params['probabilities'].get('toilet_after', 0.2)

    # Service times (min, max tuples)
    service_times = params.get('service_times', {})
    reg_time = service_times.get('registration', (1, 2))
    sec_time = service_times.get('security', (1, 5))
    customs_time = service_times.get('customs', (1, 6))
    duty_free_time = service_times.get('duty_free', (5, 15))
    restaurant_time = service_times.get('restaurant', (10, 45))
    toilet_time = service_times.get('toilet', (2, 5))
    boarding_time = service_times.get('boarding', (20 / 60, 2))

    passenger_arrival_rate = params['passenger_arrival_rate']

    class Airport(object):
        """Класс для моделирования аэропорта с различными ресурсами обслуживания"""

        def __init__(self, env, num_registration_agents,
                     num_security_agents, num_customs_agents,
                     num_duty_free_cashiers, num_restaurant_tables,
                     num_toilets_before, num_toilets_after, num_boarding_gates):
            self.env = env
            self.registration = simpy.Resource(env, num_registration_agents)
            self.security = simpy.Resource(env, num_security_agents)
            self.customs = simpy.Resource(env, num_customs_agents)
            self.duty_free = simpy.Resource(env, num_duty_free_cashiers)
            self.restaurant = simpy.Resource(env, num_restaurant_tables)
            self.toilet_before = simpy.Resource(env, num_toilets_before)
            self.toilet_after = simpy.Resource(env, num_toilets_after)
            self.boarding_gate = simpy.Resource(env, num_boarding_gates)

            # Сохраняем количество ресурсов для расчета утилизации
            self.resource_counts = {
                'registration': num_registration_agents,
                'security': num_security_agents,
                'customs': num_customs_agents,
                'duty_free': num_duty_free_cashiers,
                'restaurant': num_restaurant_tables,
                'toilet': num_toilets_before + num_toilets_after,
                'boarding': num_boarding_gates
            }

        def register_passenger(self, passenger):
            """Регистрация пассажира и багажа (мин + 1 * каждое место багажа)"""
            num_bags = random.randint(0, 3)
            service_time = random.uniform(*reg_time) + num_bags * 1
            yield self.env.timeout(service_time)

        def check_security(self, passenger):
            """Проверка безопасности"""
            service_time = random.uniform(*sec_time)
            yield self.env.timeout(service_time)

        def check_customs(self, passenger):
            """Таможенная проверка"""
            service_time = random.uniform(*customs_time)
            yield self.env.timeout(service_time)

        def visit_duty_free(self, passenger):
            """Покупки в Duty Free"""
            service_time = random.uniform(*duty_free_time)
            yield self.env.timeout(service_time)

        def use_restaurant(self, passenger):
            """Посещение ресторана"""
            service_time = random.uniform(*restaurant_time)
            yield self.env.timeout(service_time)

        def use_toilet(self, passenger):
            """Посещение туалета"""
            service_time = random.uniform(*toilet_time)
            yield self.env.timeout(service_time)

        def board_flight(self, passenger):
            """Посадка на рейс"""
            service_time = random.uniform(*boarding_time)
            yield self.env.timeout(service_time)

    def passenger_journey(env, passenger_id, airport):
        """Процесс прохождения пассажира через аэропорт"""
        nonlocal served_passengers, rejected_passengers, timeout_passengers

        arrival_time = env.now
        timed_out = False  # Флаг для отслеживания таймаута

        try:
            # Регистрация на рейс и сдача багажа (обязательно)
            reg_start = env.now
            with airport.registration.request() as request:
                # Ждем либо получения ресурса, либо истечения времени
                remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                if remaining_time <= 0:
                    timed_out = True
                    return
                result = yield request | env.timeout(remaining_time)
                if request not in result:
                    timed_out = True
                    return
                yield env.process(airport.register_passenger(passenger_id))
            service_stats['registration'].append(env.now - reg_start)

            # Посещение туалета
            if random.random() < prob_toilet_before:
                toilet_start = env.now
                with airport.toilet_before.request() as request:
                    remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                    if remaining_time <= 0:
                        timed_out = True
                        return
                    result = yield request | env.timeout(remaining_time)
                    if request not in result:
                        timed_out = True
                        return
                    yield env.process(airport.use_toilet(passenger_id))
                service_stats['toilet'].append(env.now - toilet_start)

            # Проверка безопасности (обязательно)
            sec_start = env.now
            with airport.security.request() as request:
                remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                if remaining_time <= 0:
                    timed_out = True
                    return
                result = yield request | env.timeout(remaining_time)
                if request not in result:
                    timed_out = True
                    return
                yield env.process(airport.check_security(passenger_id))
            service_stats['security'].append(env.now - sec_start)

            # Таможенная проверка для международных рейсов
            if random.random() < prob_customs:
                cust_start = env.now
                with airport.customs.request() as request:
                    remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                    if remaining_time <= 0:
                        timed_out = True
                        return
                    result = yield request | env.timeout(remaining_time)
                    if request not in result:
                        timed_out = True
                        return
                    yield env.process(airport.check_customs(passenger_id))
                service_stats['customs'].append(env.now - cust_start)

            # Покупки в Duty Free
            if random.random() < prob_duty_free:
                df_start = env.now
                with airport.duty_free.request() as request:
                    remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                    if remaining_time <= 0:
                        timed_out = True
                        return
                    result = yield request | env.timeout(remaining_time)
                    if request not in result:
                        timed_out = True
                        return
                    yield env.process(airport.visit_duty_free(passenger_id))
                service_stats['duty_free'].append(env.now - df_start)

            # Посещение ресторана
            if random.random() < prob_restaurant:
                rest_start = env.now
                with airport.restaurant.request() as request:
                    remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                    if remaining_time <= 0:
                        timed_out = True
                        return
                    result = yield request | env.timeout(remaining_time)
                    if request not in result:
                        timed_out = True
                        return
                    yield env.process(airport.use_restaurant(passenger_id))
                service_stats['restaurant'].append(env.now - rest_start)

            # Еще раз туалет перед посадкой
            if random.random() < prob_toilet_after:
                toilet_start = env.now
                with airport.toilet_after.request() as request:
                    remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                    if remaining_time <= 0:
                        timed_out = True
                        return
                    result = yield request | env.timeout(remaining_time)
                    if request not in result:
                        timed_out = True
                        return
                    yield env.process(airport.use_toilet(passenger_id))
                service_stats['toilet'].append(env.now - toilet_start)

            # Посадка на рейс (обязательно)
            board_start = env.now
            with airport.boarding_gate.request() as request:
                remaining_time = MAX_WAIT_TIME - (env.now - arrival_time)
                if remaining_time <= 0:
                    timed_out = True
                    return
                result = yield request | env.timeout(remaining_time)
                if request not in result:
                    timed_out = True
                    return
                yield env.process(airport.board_flight(passenger_id))
            service_stats['boarding'].append(env.now - board_start)

            # Сохраняем общее время пребывания пассажира в аэропорту
            total_time = env.now - arrival_time
            wait_times.append(total_time)
            served_passengers += 1

        finally:
            # Обработка таймаута
            if timed_out:
                timeout_passengers += 1
                rejected_passengers += 1

    def run_airport(env, airport, passenger_arrival_rate):
        """Генерация потока пассажиров"""
        passenger_id = 0

        # Первоначально несколько пассажиров уже в аэропорту
        for i in range(INITIAL_PASSENGERS):
            env.process(passenger_journey(env, passenger_id, airport))
            passenger_id += 1

        # Генерация новых пассажиров
        while True:
            yield env.timeout(random.expovariate(
                1.0 / passenger_arrival_rate))  # каждые passenger_arrival_rate минут приходит пассажир
            env.process(passenger_journey(env, passenger_id, airport))
            passenger_id += 1

    def calculate_statistics(wait_times, service_stats, simulation_time, resource_counts):
        """Расчет статистики системы"""
        if not wait_times:
            return None

        avg_wait_time = statistics.mean(wait_times)
        avg_passengers_in_system = len(wait_times) * avg_wait_time / simulation_time

        # Коэффициент использования для каждого типа ресурса
        utilization = {}
        for service, times in service_stats.items():
            if times and service in resource_counts:
                # Делим на количество ресурсов
                utilization[service] = sum(times) / (simulation_time * resource_counts[service])

        # Абсолютная пропускная способность (пассажиров в час)
        absolute_throughput = (served_passengers / simulation_time) * 60

        # Относительная пропускная способность
        total_passengers = served_passengers + rejected_passengers
        relative_throughput = served_passengers / total_passengers if total_passengers > 0 else 0

        return {
            'avg_wait_time': avg_wait_time,
            'avg_passengers_in_system': avg_passengers_in_system,
            'utilization': utilization,
            'absolute_throughput': absolute_throughput,
            'relative_throughput': relative_throughput,
            'served_passengers': served_passengers,
            'rejected_passengers': rejected_passengers,
            'timeout_passengers': timeout_passengers
        }

    env = simpy.Environment()
    airport = Airport(env, num_registration_agents, num_security_agents, num_customs_agents,
                      num_duty_free_cashiers, num_restaurant_tables, num_toilets_before,
                      num_toilets_after, num_boarding_gates)
    env.process(run_airport(env, airport, passenger_arrival_rate))
    env.run(until=SIMULATION_TIME)

    stats = calculate_statistics(wait_times, service_stats, SIMULATION_TIME, airport.resource_counts)
    return stats, params


def generate_grid_search_params(base_params: Dict[str, Any], grid_params: Dict[str, List]) -> List[Dict[str, Any]]:
    """
    Генерирует список параметров для grid search на базе base_config.
    """
    keys, values = zip(*grid_params.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    param_list = []
    for combo in combinations:
        params = json.loads(json.dumps(base_params))  # копия
        _update_params_recursive(params, combo)
        param_list.append(params)

    return param_list


def _update_params_recursive(target: Dict, updates: Dict):
    """
    Обновляет параметры для заданного dict.
    """
    for key, value in updates.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _update_params_recursive(target[key], value)
        else:
            target[key] = value


def run_grid_search(base_config_path: str, grid_config_path: str, num_runs_per_config: int = 1):
    """
    Запуск grid search по параметру заданному в grid_config_path,
    используя base_config_path как базу. Каждая конфигурация запускается num_runs_per_config раз.
    """
    base_params = load_params_from_json(base_config_path)
    grid_params = load_params_from_json(grid_config_path)

    param_combinations = generate_grid_search_params(base_params, grid_params)
    results = []
    total_configs = len(param_combinations)
    print(f"Запуск grid search с {total_configs} настройками...")

    for i, params in enumerate(param_combinations):
        print(f"\n--- Запуск конфигурации {i + 1}/{total_configs} ---")
        print(f"Параметры: {params}")
        config_results = {'parameters': params, 'runs': []}

        for run_num in range(num_runs_per_config):
            print(f"  Запуск {run_num + 1}/{num_runs_per_config}")
            try:
                stats, used_params = run_simulation_with_params(params)
                config_results['runs'].append({
                    'run_id': run_num + 1,
                    'statistics': stats
                })
            except Exception as e:
                print(f"    Ошибка в симуляции с конфигурацией {i + 1}, запуск {run_num + 1}: {e}")
                config_results['runs'].append({
                    'run_id': run_num + 1,
                    'error': str(e)
                })

        results.append(config_results)

    # Средние для каждой конфигурации
    averaged_results = []
    for config_result in results:
        avg_stats = None
        runs_with_stats = [r for r in config_result['runs'] if 'statistics' in r and r['statistics'] is not None]

        if runs_with_stats:
            first_run_stats = runs_with_stats[0]['statistics']
            avg_stats = {}
            for key, value in first_run_stats.items():
                if isinstance(value, (int, float)):
                    avg_val = statistics.mean(
                        [r['statistics'][key] for r in runs_with_stats if r['statistics'] is not None])
                    avg_stats[key] = avg_val
                elif isinstance(value, dict):
                    avg_dict = {}
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (int, float)):
                            avg_sub_val = statistics.mean(
                                [r['statistics'][key][sub_key] for r in runs_with_stats if r['statistics'] is not None])
                            avg_dict[sub_key] = avg_sub_val
                        else:
                            avg_dict[sub_key] = sub_value
                    avg_stats[key] = avg_dict
                else:
                    avg_stats[key] = value

        averaged_results.append({
            'parameters': config_result['parameters'],
            'averaged_statistics': avg_stats,
            'individual_runs': config_result['runs']
        })

    # Сохранение
    output_file = "grid_search_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(averaged_results, f, indent=2, ensure_ascii=False)
    print(f"\nGrid search results saved to '{output_file}'")
    return averaged_results


def run_batch_experiments(json_file_path: str):
    """
    Запуск экспериментов из batch json.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        batch_params = json.load(f)

    if not isinstance(batch_params, list):
        print("Error: Batch JSON должен иметь список словарей параметров.")
        return

    results = []
    for i, params in enumerate(batch_params):
        print(f"\n--- Запуск эксперимента {i + 1}/{len(batch_params)} ---")
        try:
            stats, used_params = run_simulation_with_params(params)
            results.append({
                'experiment_id': i + 1,
                'parameters': used_params,
                'statistics': stats
            })
        except Exception as e:
            print(f"Ошибка при выполнении эксперимента {i + 1}: {e}")
            results.append({
                'experiment_id': i + 1,
                'parameters': params,
                'error': str(e)
            })

    output_file = "batch_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nBatch experiment results saved to '{output_file}'")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python airport_simulator.py single <config_file.json>")
        print("  python airport_simulator.py batch <batch_config.json>")
        print("  python airport_simulator.py grid <base_config.json> <grid_config.json> [num_runs_per_config]")
        print("  - single: Run a single simulation.")
        print("  - batch: Run a list of simulations from a batch file.")
        print("  - grid: Run a grid search using base and grid config files.")
        print("  - num_runs_per_config: Optional, number of runs per configuration for averaging (default 1).")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'single':
        if len(sys.argv) < 3:
            print("Usage: python airport_simulator.py single <config_file.json>")
            sys.exit(1)
        json_file_path = sys.argv[2]
        params = load_params_from_json(json_file_path)
        stats, used_params = run_simulation_with_params(params)
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ МОДЕЛИРОВАНИЯ АЭРОПОРТА")
        print("=" * 60)
        if stats:
            mins, secs = divmod(stats['avg_wait_time'], 1)
            secs = secs * 60
            print(f"\nСреднее время пребывания пассажира: {int(mins)} мин {int(secs)} сек")
            print(f"Среднее число пассажиров в системе: {stats['avg_passengers_in_system']:.2f}")
            print(f"Обслужено пассажиров: {stats['served_passengers']}")
            print(f"Не обслужено пассажиров: {stats['rejected_passengers']}")
            print(f"  - из них ушедших по таймауту: {stats['timeout_passengers']}")
            print(f"\nАбсолютная пропускная способность: {stats['absolute_throughput']:.2f} пасс/час")
            print(f"Относительная пропускная способность: {stats['relative_throughput']:.2%}")
            print("\nКоэффициенты использования ресурсов:")
            for service, util in stats['utilization'].items():
                print(f"  {service:15s}: {util:.2%}")
        else:
            print("Недостаточно данных для статистики")

    elif command == 'batch':
        if len(sys.argv) < 3:
            print("Usage: python airport_simulator.py batch <batch_config.json>")
            sys.exit(1)
        json_file_path = sys.argv[2]
        run_batch_experiments(json_file_path)

    elif command == 'grid':
        if len(sys.argv) < 4:
            print("Usage: python airport_simulator.py grid <base_config.json> <grid_config.json> [num_runs_per_config]")
            sys.exit(1)
        base_config_path = sys.argv[2]
        grid_config_path = sys.argv[3]
        num_runs = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        run_grid_search(base_config_path, grid_config_path, num_runs)

    else:
        print("Invalid command. Use 'single', 'batch', or 'grid'.")
        sys.exit(1)


if __name__ == "__main__":
    main()