import pygame
import pymunk
import pymunk.pygame_util
import math
import random

from mpmath.libmp import normalize
from pygame.math import clamp

WIDTH, HEIGHT = 800, 600
drone_width = 100
drone_height = 20
min_wind_force = 500
max_wind_force = 1000
wind_range = max_wind_force - min_wind_force
# fx, fy = 0, 0
point = (0, 0)
FPS = 60

kp_x = -1.5/80
ki_x = -0.5/80
kd_x = -65/80

kp_y = 5/80
ki_y = 20/80
kd_y = 500/80

kp_angle = -500/80
ki_angle = -400/80
kd_angle = -5500/80

export_csv = True

# culori
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 100, 255, 255)
RED = (255, 0, 0)

def create_drone(space, x, y):
    body = pymunk.Body(8, pymunk.moment_for_box(8, (100, 20)))  # masă si moment de inerție
    body.position = x, y

    shape = pymunk.Poly.create_box(body, (drone_width, drone_height))
    shape.color = BLUE
    shape.elasticity = 0.5
    shape.friction = 0.5
    space.add(body, shape)

    return body


def draw_arrow(screen, start_pos, force, color):
    fx, fy = force
    max_length = 80 #lungimea maxima a sagetii in px

    # normalizarea fortei pentru a se incadra in cadran
    normalized_fx = (fx / max_wind_force) * max_length
    normalized_fy = (fy / max_wind_force) * max_length

    end_pos = (start_pos[0] + normalized_fx, start_pos[1] - normalized_fy)

    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    angle = math.atan2(dy, dx)

    length = math.hypot(dx, dy)

    pygame.draw.line(screen, color, start_pos, end_pos, 2)

    arrowhead_length = length * 0.15
    arrowhead_left = (end_pos[0] - arrowhead_length * math.cos(angle - math.pi / 6),
                      end_pos[1] - arrowhead_length * math.sin(angle - math.pi / 6))
    arrowhead_right = (end_pos[0] - arrowhead_length * math.cos(angle + math.pi / 6),
                       end_pos[1] - arrowhead_length * math.sin(angle + math.pi / 6))

    pygame.draw.polygon(screen, color, [end_pos, arrowhead_left, arrowhead_right])


def simulate_wind(drone, wind_on, fx, fy):
    if wind_on:
        drone.apply_force_at_world_point((fx, fy), drone.position)


def generateForces():
    rnd_x_force = 0
    while rnd_x_force == 0:
        rnd_x_force = random.randint(-1, 1) * random.randint(min_wind_force, max_wind_force)
    print("rnd_x_force", rnd_x_force)

    rnd_y_force = 0
    while rnd_y_force == 0:
        rnd_y_force = random.randint(-1, 1) * random.randint(min_wind_force, max_wind_force)
    print("rnd_y_force", rnd_y_force)
    return rnd_x_force, rnd_y_force


def PID_control_x(errors_x):
    clamped_errors_x = [clamp(i, -100, 100) for i in errors_x]
    PID_x = kp_x * clamped_errors_x[0] + ki_x * (clamped_errors_x[0] + clamped_errors_x[1] + clamped_errors_x[2]) + kd_x * (clamped_errors_x[0] - clamped_errors_x[2])
    return PID_x


def PID_control_y(errors_y):

    clamped_errors_y = [clamp(i, -100, 100) for i in errors_y]
    PID_y = kp_y * clamped_errors_y[0] + ki_y * (clamped_errors_y[0] + clamped_errors_y[1] + clamped_errors_y[2]) + kd_y * (clamped_errors_y[0] - clamped_errors_y[2])

    return PID_y


def PID_control_angle(errors_angle):
    PID_angle = kp_angle * errors_angle[0] + ki_angle * (
                errors_angle[0] + errors_angle[1] + errors_angle[2]) + kd_angle * (errors_angle[0] - errors_angle[2])
    return PID_angle

def controller(input) -> (float, float):
    pid_ctrl_x_output = PID_control_x(input[0:3])
    pid_ctrl_y_output = PID_control_y(input[3:6])
    pid_ctrl_angle_output = PID_control_angle(input[6:9])

    thruster_left = pid_ctrl_y_output + pid_ctrl_x_output + pid_ctrl_angle_output
    thruster_right = pid_ctrl_y_output - pid_ctrl_x_output - pid_ctrl_angle_output

    thruster_left = clamp(thruster_left, -80, 0)
    thruster_right = clamp(thruster_right, -80, 0)

    return thruster_left, thruster_right


def main():
    fx, fy = 0, 0
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    target_position = [WIDTH / 2, HEIGHT / 2]
    target_angle = 0

    space = pymunk.Space()
    space.gravity = (0, 981)

    ground = pymunk.Segment(space.static_body, (0, HEIGHT), (WIDTH, HEIGHT), 10)
    ground.elasticity = 1.0
    ground.friction = 1.0
    space.add(ground)

    wall_1 = pymunk.Segment(space.static_body, (WIDTH, HEIGHT), (WIDTH, 0), 10)
    wall_1.elasticity = 1.0
    wall_1.friction = 1.0
    space.add(wall_1)

    wall_2 = pymunk.Segment(space.static_body, (0, 0), (0, HEIGHT), 10)
    wall_2.elasticity = 1.0
    wall_2.friction = 1.0
    space.add(wall_2)

    tavan = pymunk.Segment(space.static_body, (0, 0), (WIDTH, 0), 10)
    tavan.elasticity = 1.0
    tavan.friction = 1.0
    space.add(tavan)

    drone = create_drone(space, WIDTH // 2, HEIGHT // 2)

    draw_options = pymunk.pygame_util.DrawOptions(screen)

    running = True
    wind_on = True
    reverse = 1

    start_time = pygame.time.get_ticks()

    #############
    current_x = drone.position.x
    current_y = drone.position.y
    current_angle = drone.angle
    errors_x = [target_position[0] - current_x, target_position[0] - current_x, target_position[0] - current_x]
    errors_y = [target_position[1] - current_y, target_position[1] - current_y, target_position[1] - current_y]
    normalized_angle = current_angle
    errors_angle = [normalized_angle - target_angle, normalized_angle - target_angle, normalized_angle - target_angle]
    ##############

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    reverse = -reverse
                    print("Reverse: ", reverse)
                if event.key == pygame.K_a:  #miscaa la stanga
                    target_position[0] -= 150
                    print("KEY A pressed")
                if event.key == pygame.K_d:  #misca la dreapta
                    target_position[0] += 150
                    print("KEY D pressed")
                if event.key == pygame.K_w:  #misca sus
                    target_position[1] -= 150
                    print("KEY W pressed")
                if event.key == pygame.K_s:  #misca jos
                    target_position[1] += 150
                    print("KEY S pressed")

        ##############################

        current_x = drone.position.x
        for i in range(2, 0, -1):
            errors_x[i] = errors_x[i - 1]
        errors_x[0] = target_position[0] - current_x

        current_y = drone.position.y
        for i in range(2, 0, -1):
            errors_y[i] = errors_y[i - 1]
        errors_y[0] = target_position[1] - current_y

        current_angle = drone.angle
        for i in range(2, 0, -1):
            errors_angle[i] = errors_angle[i - 1]

        errors_angle[0] = target_angle - current_angle

        input_x = [clamp(i, -100, 100) / 100 for i in errors_x]
        input_y = [clamp(i, -100, 100) / 100 for i in errors_y]
        input_angle = [i / 100 for i in errors_angle]
        input_all = input_x + input_y + input_angle

        (thruster_left, thruster_right) = controller(input_all)

        if export_csv:
            with open('data.csv', 'a') as f:
                f.write(f"{input_all[0]},{input_all[1]},{input_all[2]},{input_all[3]},{input_all[4]},{input_all[5]},{input_all[6]},{input_all[7]},{input_all[8]},{thruster_left},{thruster_right}\n")

        print(f"L:{thruster_left:4.1f} R:{thruster_right:4.1f} x:{errors_x[0]:4.1f} y:{errors_y[0]:4.1f} w:{errors_angle[0]:4.1f}")

        thruster_left *= 8000
        thruster_right *= 8000

        drone.apply_force_at_local_point((0, thruster_left), (-50, 0))
        drone.apply_force_at_local_point((0, thruster_right), (50, 0))
        ###################################

        # TODO WIND
        elapsed_time = (pygame.time.get_ticks() - start_time) / 1000
        if elapsed_time >= 5:
            print("10 seconds have passed! Changing the wind!")
            [fx, fy] = generateForces()
            print("Forta pe x: ", fx, "\n", "Forta pe y: ", fy, "\n")
            start_time = pygame.time.get_ticks()
        simulate_wind(drone, wind_on, fx, fy)
        print(fx, fy)

        space.step(1 / FPS)

        screen.fill(WHITE)
        space.debug_draw(draw_options)
        if wind_on:
            rectangle = pygame.Rect(0, 0, 160, 160)
            pygame.draw.rect(screen, RED, rectangle, 2)
            draw_arrow(screen, (80, 80), (fx, fy), RED)
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()