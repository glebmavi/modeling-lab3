import simpy
import random
import statistics
import json
from typing import List, Dict, Any


def load_params_from_json(json_file_path: str) -> Dict[str, Any]:
    """
    Load simulation parameters from a JSON file.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        params = json.load(f)
    return params


def run_simulation_with_params(params: Dict[str, Any]):
    """
    Run the airport simulation with given parameters.
    Encapsulates the original main logic but uses passed parameters.
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
            yield env.timeout(random.expovariate(1.0 / passenger_arrival_rate)) # каждые passenger_arrival_rate минут приходит пассажир
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


def print_statistics(stats, params):
    """Вывод статистики"""
    if stats is None:
        print("Недостаточно данных для статистики")
        return

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ МОДЕЛИРОВАНИЯ АЭРОПОРТА")
    print("=" * 60)

    mins, secs = divmod(stats['avg_wait_time'], 1)
    secs = secs * 60
    print(f"\nСреднее время пребывания пассажира: {int(mins)} мин {int(secs)} сек")
    print(f"Среднее число пассажиров в системе: {stats['avg_passengers_in_system']:.2f}")
    print(f"Обслужено пассажиров: {stats['served_passengers']}")
    print(f"Не обслужено пассажиров: {stats['rejected_passengers']}")
    print(f"  - из них ушедших по таймауту (>{params.get('max_time', 180)} мин): {stats['timeout_passengers']}")
    print(f"\nАбсолютная пропускная способность: {stats['absolute_throughput']:.2f} пасс/час")
    print(f"Относительная пропускная способность: {stats['relative_throughput']:.2%}")

    print("\nКоэффициенты использования ресурсов:")
    for service, util in stats['utilization'].items():
        print(f"  {service:15s}: {util:.2%}")


def run_batch_experiments(json_file_path: str):
    """
    Run multiple experiments from a batch JSON file.
    The batch file should contain a list of parameter dictionaries.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        batch_params = json.load(f)

    if not isinstance(batch_params, list):
        print("Error: Batch JSON file must contain a list of parameter dictionaries.")
        return

    results = []
    for i, params in enumerate(batch_params):
        print(f"\n--- Running Experiment {i + 1}/{len(batch_params)} ---")
        try:
            stats, used_params = run_simulation_with_params(params)
            results.append({
                'experiment_id': i + 1,
                'parameters': used_params,
                'statistics': stats
            })
            print_statistics(stats, used_params)
        except Exception as e:
            print(f"Error running experiment {i + 1}: {e}")
            results.append({
                'experiment_id': i + 1,
                'parameters': params,
                'error': str(e)
            })

    # Optionally, save results to a file
    output_file = "batch_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nBatch experiment results saved to '{output_file}'")


def main():
    """Main function to run either a single simulation or batch experiments."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python airport_simulation.py <config_file.json> [batch]")
        print("  config_file.json: Path to the JSON configuration file")
        print("  [batch]: Optional argument. If 'batch', runs batch experiments.")
        sys.exit(1)

    json_file_path = sys.argv[1]
    is_batch = len(sys.argv) > 2 and sys.argv[2].lower() == 'batch'

    if is_batch:
        run_batch_experiments(json_file_path)
    else:
        # Run a single simulation
        params = load_params_from_json(json_file_path)
        stats, used_params = run_simulation_with_params(params)
        print_statistics(stats, used_params)


if __name__ == "__main__":
    main()