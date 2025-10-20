import simpy
import random
import statistics
from typing import List, Dict

# Глобальные списки для хранения статистики
wait_times = []  # Общее время ожидания пассажира в системе
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


class Airport(object):
    """Класс для моделирования аэропорта с различными ресурсами обслуживания"""

    def __init__(self, env, num_registration_agents,
                 num_security_agents, num_customs_agents,
                 num_duty_free_cashiers, num_restaurant_tables,
                 num_toilets_before, num_toilets_after, num_boarding_gates):
        self.env = env
        # Ресурсы аэропорта с отдельными агентами обслуживания
        self.registration = simpy.Resource(env, num_registration_agents)
        self.security = simpy.Resource(env, num_security_agents)
        self.customs = simpy.Resource(env, num_customs_agents)

        self.duty_free = simpy.Resource(env, num_duty_free_cashiers)
        self.restaurant = simpy.Resource(env, num_restaurant_tables)
        self.toilet_before = simpy.Resource(env, num_toilets_before)
        self.toilet_after = simpy.Resource(env, num_toilets_after)
        self.boarding_gate = simpy.Resource(env, num_boarding_gates)

    def register_passenger(self, passenger):
        """Регистрация пассажира и багажа (1-3 мин + 1 мин за каждое место багажа)"""
        num_bags = random.randint(0, 3)
        service_time = random.uniform(1, 3) + num_bags * 1
        yield self.env.timeout(service_time)

    def check_security(self, passenger):
        """Проверка безопасности"""
        service_time = random.uniform(2, 5)
        yield self.env.timeout(service_time)

    def check_customs(self, passenger):
        """Таможенная проверка"""
        service_time = random.uniform(2, 6)
        yield self.env.timeout(service_time)

    def visit_duty_free(self, passenger):
        """Покупки в Duty Free"""
        service_time = random.uniform(5, 15)
        yield self.env.timeout(service_time)

    def use_restaurant(self, passenger):
        """Посещение ресторана"""
        service_time = random.uniform(10, 45)
        yield self.env.timeout(service_time)

    def use_toilet(self, passenger):
        """Посещение туалета"""
        service_time = random.uniform(2, 5)
        yield self.env.timeout(service_time)

    def board_flight(self, passenger):
        """Посадка на рейс"""
        service_time = random.uniform(20 / 60, 2)
        yield self.env.timeout(service_time)


def passenger_journey(env, passenger_id, airport):
    """Процесс прохождения пассажира через аэропорт"""
    global served_passengers, rejected_passengers

    arrival_time = env.now

    try:
        # 1. Регистрация на рейс и сдача багажа (обязательно)
        reg_start = env.now
        with airport.registration.request() as request:
            yield request
            yield env.process(airport.register_passenger(passenger_id))
        service_stats['registration'].append(env.now - reg_start)

        # 2. Проверка безопасности (обязательно)
        sec_start = env.now
        with airport.security.request() as request:
            yield request
            yield env.process(airport.check_security(passenger_id))
        service_stats['security'].append(env.now - sec_start)

        # 3. Таможенная проверка для международных рейсов (70% пассажиров)
        if random.random() < 0.7:
            cust_start = env.now
            with airport.customs.request() as request:
                yield request
                yield env.process(airport.check_customs(passenger_id))
            service_stats['customs'].append(env.now - cust_start)

        # 4. Посещение туалета (30% пассажиров, в любой момент)
        if random.random() < 0.3:
            toilet_start = env.now
            with airport.toilet_before.request() as request:
                yield request
                yield env.process(airport.use_toilet(passenger_id))
            service_stats['toilet'].append(env.now - toilet_start)

        # 5. Покупки в Duty Free (20% пассажиров)
        if random.random() < 0.2:
            df_start = env.now
            with airport.duty_free.request() as request:
                yield request
                yield env.process(airport.visit_duty_free(passenger_id))
            service_stats['duty_free'].append(env.now - df_start)

        # 6. Посещение ресторана (40% пассажиров)
        if random.random() < 0.4:
            rest_start = env.now
            with airport.restaurant.request() as request:
                yield request
                yield env.process(airport.use_restaurant(passenger_id))
            service_stats['restaurant'].append(env.now - rest_start)

        # 7. Еще раз туалет перед посадкой (30% пассажиров)
        if random.random() < 0.3:
            toilet_start = env.now
            with airport.toilet_after.request() as request:
                yield request
                yield env.process(airport.use_toilet(passenger_id))
            service_stats['toilet'].append(env.now - toilet_start)

        # 8. Посадка на рейс (обязательно)
        board_start = env.now
        with airport.boarding_gate.request() as request:
            yield request
            yield env.process(airport.board_flight(passenger_id))
        service_stats['boarding'].append(env.now - board_start)

        # Сохраняем общее время пребывания пассажира в аэропорту
        total_time = env.now - arrival_time
        wait_times.append(total_time)
        served_passengers += 1

    except simpy.Interrupt:
        rejected_passengers += 1


def run_airport(env, airport, passenger_arrival_rate):
    """Генерация потока пассажиров"""
    passenger_id = 0

    # Первоначально несколько пассажиров уже в аэропорту
    for i in range(200):
        env.process(passenger_journey(env, passenger_id, airport))
        passenger_id += 1

    # Генерация новых пассажиров
    while True:
        yield env.timeout(random.expovariate(1.0 / passenger_arrival_rate))
        env.process(passenger_journey(env, passenger_id, airport))
        passenger_id += 1


def calculate_statistics(wait_times, service_stats, simulation_time):
    """Расчет статистики системы"""
    if not wait_times:
        return None

    avg_wait_time = statistics.mean(wait_times)
    avg_passengers_in_system = len(wait_times) * avg_wait_time / simulation_time

    # Коэффициент использования для каждого типа ресурса
    utilization = {}
    for service, times in service_stats.items():
        if times:
            utilization[service] = sum(times) / simulation_time

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
        'rejected_passengers': rejected_passengers
    }


def print_statistics(stats):
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
    print(f"\nАбсолютная пропускная способность: {stats['absolute_throughput']:.2f} пасс/час")
    print(f"Относительная пропускная способность: {stats['relative_throughput']:.2%}")

    print("\nКоэффициенты использования ресурсов:")
    for service, util in stats['utilization'].items():
        print(f"  {service:15s}: {util:.2%}")


def get_user_input():
    """Получение параметров от пользователя"""
    print("\nВведите количество ресурсов аэропорта:")
    print("(Нажмите Enter для значений по умолчанию)")

    try:
        num_registration = input("Стойки регистрации [3]: ") or "3"
        num_security = input("Пункты безопасности [4]: ") or "4"
        num_customs = input("Таможенные службы [2]: ") or "2"
        num_duty_free = input("Магазины Duty Free [2]: ") or "2"
        num_restaurants = input("Рестораны [3]: ") or "3"
        num_toilets_before = input("Туалеты до регистрации [3]: ") or "3"
        num_toilets_after = input("Туалеты после регистрации [3]: ") or "3"
        num_boarding_gates = input("Выходы на посадку [4]: ") or "4"
        passenger_arrival_rate = input("Интервал прибытия пассажиров в мин [2.0]: ") or "2.0"

        params = [num_registration, num_security, num_customs, num_duty_free,
                  num_restaurants, num_toilets_before, num_toilets_after, num_boarding_gates, passenger_arrival_rate]

        if all(str(p).replace('.', '').isdigit() for p in params):
            params = [int(x) if '.' not in str(x) else float(x) for x in params]
            return params
        else:
            raise ValueError

    except (ValueError, KeyboardInterrupt):
        print("\nИспользуются значения по умолчанию.")
        return [3, 4, 2, 2, 3, 3, 3, 4, 2.0]


def main():
    """Главная функция"""
    global wait_times, service_stats, served_passengers, rejected_passengers

    # Сброс глобальных переменных
    wait_times = []
    service_stats = {k: [] for k in service_stats.keys()}
    served_passengers = 0
    rejected_passengers = 0

    random.seed(42)

    # Получение параметров
    params = get_user_input()
    num_registration, num_security, num_customs, num_duty_free, \
        num_restaurants, num_toilets_before, num_toilets_after, num_boarding_gates, passenger_arrival_rate = params

    # Создание среды и запуск моделирования
    print("\nЗапуск моделирования...")
    simulation_time = 480  # 8 часов работы аэропорта

    env = simpy.Environment()
    airport = Airport(env, num_registration, num_security, num_customs,
                      num_duty_free, num_restaurants, num_toilets_before,
                      num_toilets_after, num_boarding_gates)
    env.process(run_airport(env, airport, passenger_arrival_rate))
    env.run(until=simulation_time)

    # Расчет и вывод статистики
    stats = calculate_statistics(wait_times, service_stats, simulation_time)
    print_statistics(stats)

    # Рекомендации по оптимизации
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ")
    print("=" * 60)

    if stats and stats['utilization']:
        bottlenecks = {k: v for k, v in stats['utilization'].items() if v > 0.8}
        if bottlenecks:
            print("\nУзкие места (загрузка > 80%):")
            for service, util in bottlenecks.items():
                print(f"  - {service}: {util:.2%} → рекомендуется увеличить количество")
        else:
            print("\nСистема работает эффективно, узких мест не обнаружено.")

    print("=" * 60)


if __name__ == "__main__":
    main()