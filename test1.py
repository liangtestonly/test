#msltest2.py
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import json
import os
from dataclasses import dataclass

# --- Simulation Constants ---
EARTH_RADIUS = 6.371  # Normalized or scaled units (e.g., thousands of km)
EARTH_RADIUS_KM = 6371.0
TIME_STEP = 0.1


@dataclass
class SimulationConfig:
    missile_speed: float = 0.05
    interceptor_speed: float = 0.07
    proportional_gain: float = 4.0
    auto_launch_interceptor: bool = True
    missile_start_lat: float = 39.0
    missile_start_lon: float = 125.0
    missile_start_altitude_km: float = 0.0
    missile_target_lat: float = 38.0
    missile_target_lon: float = -77.0
    missile_target_altitude_km: float = 0.0
    interceptor_start_lat: float = 64.0
    interceptor_start_lon: float = -147.0
    interceptor_start_altitude_km: float = 0.0
    interceptor_delay_sec: float = 3.0
    custom_cam_lat: float = 38.54
    custom_cam_lon: float = 100.74
    custom_cam_altitude_km: float = 0.5
    custom_view_yaw_deg: float = 169.26
    custom_view_pitch_deg: float = 38.54
    missile_loft_factor: float = 0.8
    missile_hit_radius: float = 0.0015
    interceptor_hit_radius: float = 0.003
    loft_vis_ratio: float = 1.0
    spd_vis_ratio: float = 1.0


def altitude_km_to_radius(altitude_km, base_radius=EARTH_RADIUS):
    return base_radius * (1.0 + float(altitude_km) / EARTH_RADIUS_KM)


def lat_lon_to_xyz(lat, lon, radius=EARTH_RADIUS, altitude_km=0.0):
    """Converts latitude and longitude (in degrees) to 3D Cartesian coordinates."""
    radius = altitude_km_to_radius(altitude_km, radius)
    phi = math.radians(90 - lat)
    theta = math.radians(lon)
    x = radius * math.sin(phi) * math.cos(theta)
    y = radius * math.cos(phi)
    z = radius * math.sin(phi) * math.sin(theta)
    return np.array([x, y, z], dtype=np.float32)


def xyz_to_lat_lon(point):
    radius = np.linalg.norm(point)
    if radius < 1e-9:
        return None
    lat = math.degrees(math.asin(float(point[1]) / radius))
    lon = math.degrees(math.atan2(float(point[2]), float(point[0])))
    return float(lat), float(lon)


def draw_sphere(radius, longitudinal_lines=24, latitudinal_lines=24):
    """Draws a wireframe sphere representing the Earth."""
    glColor3f(0.3, 0.3, 0.3)
    for i in range(latitudinal_lines + 1):
        lat = -90 + i * (180 / latitudinal_lines)
        glBegin(GL_LINE_LOOP)
        for j in range(longitudinal_lines):
            lon = j * (360 / longitudinal_lines)
            glVertex3fv(lat_lon_to_xyz(lat, lon, radius))
        glEnd()

    for j in range(longitudinal_lines):
        glBegin(GL_LINE_STRIP)
        for i in range(latitudinal_lines + 1):
            lat = -90 + i * (180 / latitudinal_lines)
            lon = j * (360 / longitudinal_lines)
            glVertex3fv(lat_lon_to_xyz(lat, lon, radius))
        glEnd()


def draw_location_marker(lat, lon, color, altitude_km=0.0, radius_scale=1.04):
    base = lat_lon_to_xyz(lat, lon, EARTH_RADIUS)
    altitude_km = max(float(altitude_km), 0.0)
    visual_altitude_km = 0.0 if altitude_km == 0.0 else min(40.0 + math.sqrt(altitude_km) * 18.0, 320.0)
    marker_radius = altitude_km_to_radius(visual_altitude_km, EARTH_RADIUS)
    point = lat_lon_to_xyz(lat, lon, marker_radius)
    glColor3f(*color)
    if visual_altitude_km > 0.0:
        stem_point = lat_lon_to_xyz(lat, lon, altitude_km_to_radius(visual_altitude_km, EARTH_RADIUS * radius_scale))
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3fv(base)
        glVertex3fv(stem_point)
        glEnd()
    glPointSize(10.0 if altitude_km == 0.0 else 12.0)
    glBegin(GL_POINTS)
    glVertex3fv(point)
    glEnd()


def intersect_ray_with_sphere(ray_origin, ray_dir, radius):
    a = float(np.dot(ray_dir, ray_dir))
    b = 2.0 * float(np.dot(ray_origin, ray_dir))
    c = float(np.dot(ray_origin, ray_origin) - radius * radius)
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return None
    sqrt_disc = math.sqrt(discriminant)
    roots = [(-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a)]
    hits = [t for t in roots if t >= 0.0]
    if not hits:
        return None
    return ray_origin + ray_dir * min(hits)


def unproject_point(win_x, win_y, win_z, modelview, projection, viewport):
    x_ndc = 2.0 * (win_x - viewport[0]) / viewport[2] - 1.0
    y_ndc = 2.0 * (win_y - viewport[1]) / viewport[3] - 1.0
    z_ndc = 2.0 * win_z - 1.0
    clip = np.array([x_ndc, y_ndc, z_ndc, 1.0], dtype=float)
    inv = np.linalg.inv(projection @ modelview)
    world = inv @ clip
    if abs(world[3]) < 1e-9:
        return None
    return world[:3] / world[3]


def pick_point_on_globe(title, initial_lat, initial_lon):
    pygame.init()
    display = (1024, 768)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)

    glEnable(GL_DEPTH_TEST)
    gluPerspective(45, display[0] / display[1], 0.1, 50.0)

    clock = pygame.time.Clock()
    rotation_x = 24.0
    rotation_y = -58.0
    zoom = -18.0
    dragging = False
    selected_lat = float(initial_lat)
    selected_lon = float(initial_lon)

    running = True
    picked_value = None
    while running:
        pygame.display.set_caption(
            f"{title} | Lat {selected_lat:.2f}, Lon {selected_lon:.2f} | Right-drag rotate | Wheel zoom | Left-click pick | Esc cancel"
        )
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:
                    dragging = True
                elif event.button == 1:
                    viewport = np.array(glGetIntegerv(GL_VIEWPORT), dtype=float)
                    modelview = np.array(glGetDoublev(GL_MODELVIEW_MATRIX), dtype=float)
                    projection = np.array(glGetDoublev(GL_PROJECTION_MATRIX), dtype=float)
                    win_x = float(event.pos[0])
                    win_y = float(viewport[3] - event.pos[1])
                    near = unproject_point(win_x, win_y, 0.0, modelview, projection, viewport)
                    far = unproject_point(win_x, win_y, 1.0, modelview, projection, viewport)
                    if near is not None and far is not None:
                        ray_dir = far - near
                        norm = np.linalg.norm(ray_dir)
                        if norm > 1e-9:
                            ray_dir /= norm
                            hit = intersect_ray_with_sphere(near, ray_dir, EARTH_RADIUS)
                            if hit is not None:
                                geo = xyz_to_lat_lon(hit)
                                if geo is not None:
                                    selected_lat, selected_lon = geo
                                    picked_value = (selected_lat, selected_lon)
                                    running = False
                elif event.button == 4:
                    zoom = min(zoom + 0.8, -8.0)
                elif event.button == 5:
                    zoom = max(zoom - 0.8, -32.0)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx, dy = event.rel
                rotation_y += dx * 0.35
                rotation_x = max(min(rotation_x + dy * 0.25, 89.0), -89.0)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0.0, 0.0, zoom)
        glRotatef(rotation_x, 1.0, 0.0, 0.0)
        glRotatef(rotation_y, 0.0, 1.0, 0.0)

        draw_sphere(EARTH_RADIUS)
        draw_location_marker(selected_lat, selected_lon, (1.0, 0.9, 0.0), radius_scale=1.06)

        pygame.display.flip()
        clock.tick(60)

    pygame.display.quit()
    return picked_value


class TargetMissile:
    def __init__(self, start_lat, start_lon, start_altitude_km, target_lat, target_lon, target_altitude_km, speed, loft_factor=0.8, hit_radius=0.0015):
        self.pos = lat_lon_to_xyz(start_lat, start_lon, altitude_km=start_altitude_km)
        self.target = lat_lon_to_xyz(target_lat, target_lon, altitude_km=target_altitude_km)
        self.speed = speed
        self.loft_factor = loft_factor
        self.hit_radius = hit_radius
        self.path = [np.copy(self.pos)]
        self.active = True
        self.reached_target = False

    def update(self):
        if not self.active:
            return False

        direction = self.target - self.pos
        distance = np.linalg.norm(direction)
        if distance < self.hit_radius:
            self.active = False
            self.reached_target = True
            return True

        direction /= distance
        center_dir = self.pos / np.linalg.norm(self.pos)
        ratio = max(0.0, 1.0 - distance / EARTH_RADIUS)
        loft_force = center_dir * self.speed * self.loft_factor * math.sin(math.pi * ratio)
        self.pos += (direction * self.speed + loft_force) * TIME_STEP
        self.path.append(np.copy(self.pos))
        return False

    def draw(self):
        glColor3f(1.0, 0.0, 0.0)
        glLineWidth(3.0)
        glBegin(GL_LINE_STRIP)
        for p in self.path:
            glVertex3fv(p)
        glEnd()
        glPointSize(12.0)
        glBegin(GL_POINTS)
        glVertex3fv(self.pos)
        glEnd()
        glLineWidth(1.0)


class Interceptor:
    def __init__(self, start_lat, start_lon, start_altitude_km, speed, proportional_gain, hit_radius=0.003):
        self.pos = lat_lon_to_xyz(start_lat, start_lon, altitude_km=start_altitude_km)
        self.path = [np.copy(self.pos)]
        self.vel = np.array([0.0, 0.0, 0.0])
        self.speed = speed
        self.proportional_gain = proportional_gain
        self.hit_radius = hit_radius
        self.active = False
        self.hit = False

    def launch(self):
        self.active = True

    def update(self, target_pos):
        if not self.active or self.hit:
            return

        los = target_pos - self.pos
        distance = np.linalg.norm(los)
        if distance < self.hit_radius:
            self.hit = True
            print("Intercept successful!")
            return

        los_direction = los / distance
        desired_vel = los_direction * self.speed
        self.vel = self.vel + (desired_vel - self.vel) * self.proportional_gain * TIME_STEP
        if np.linalg.norm(self.vel) > 0:
            self.vel = (self.vel / np.linalg.norm(self.vel)) * self.speed

        self.pos += self.vel * TIME_STEP
        self.path.append(np.copy(self.pos))

    def draw(self):
        if not self.active:
            return

        glColor3f(0.0, 0.5, 1.0)
        glLineWidth(3.0)
        glBegin(GL_LINE_STRIP)
        for p in self.path:
            glVertex3fv(p)
        glEnd()
        glPointSize(12.0)
        glBegin(GL_POINTS)
        if self.hit:
            glColor3f(1.0, 1.0, 0.0)
        glVertex3fv(self.pos)
        glEnd()
        glLineWidth(1.0)


def draw_center_mark(display_width, display_height):
    """Draws a tactical HUD target reticle in the exact center of the screen."""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, display_width, 0, display_height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)

    cx = display_width / 2.0
    cy = display_height / 2.0
    gap = 4.0
    length = 12.0

    glColor3f(0.0, 1.0, 0.0)  # Tactical green reticle
    glLineWidth(2.0)
    glBegin(GL_LINES)
    # Left segment
    glVertex2f(cx - length - gap, cy)
    glVertex2f(cx - gap, cy)
    # Right segment
    glVertex2f(cx + gap, cy)
    glVertex2f(cx + length + gap, cy)
    # Bottom segment
    glVertex2f(cx, cy - length - gap)
    glVertex2f(cx, cy - gap)
    # Top segment
    glVertex2f(cx, cy + gap)
    glVertex2f(cx, cy + length + gap)
    glEnd()

    # Center dot
    glPointSize(3.0)
    glBegin(GL_POINTS)
    glVertex2f(cx, cy)
    glEnd()

    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def run_simulation(config: SimulationConfig):
    pygame.init()
    display = (1024, 768)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("3D Global Missile Intercept Simulation")

    glEnable(GL_DEPTH_TEST)

    missile = TargetMissile(
        start_lat=config.missile_start_lat,
        start_lon=config.missile_start_lon,
        start_altitude_km=config.missile_start_altitude_km,
        target_lat=config.missile_target_lat,
        target_lon=config.missile_target_lon,
        target_altitude_km=config.missile_target_altitude_km,
        speed=config.missile_speed,
        loft_factor=config.missile_loft_factor * config.loft_vis_ratio,
        hit_radius=config.missile_hit_radius,
    )
    interceptor = Interceptor(
        start_lat=config.interceptor_start_lat,
        start_lon=config.interceptor_start_lon,
        start_altitude_km=config.interceptor_start_altitude_km,
        speed=config.interceptor_speed,
        proportional_gain=config.proportional_gain,
        hit_radius=config.interceptor_hit_radius,
    )

    clock = pygame.time.Clock()
    rotation_x = config.custom_view_pitch_deg
    rotation_y = config.custom_view_yaw_deg
    zoom = -18.0
    fov = 45.0
    interceptor_launched = False

    camera_modes = [
        "orbit",
        "ground_interceptor_track",
        "ground_interceptor_look",
        "ground_target_track",
        "ground_target_look",
        "ground_missile_track",
        "ground_missile_look",
        "ground_custom_track",
        "ground_custom_look"
    ]
    camera_mode_idx = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and not interceptor_launched:
                    interceptor.launch()
                    interceptor_launched = True
                elif event.key == pygame.K_c:
                    camera_mode_idx = (camera_mode_idx + 1) % len(camera_modes)
                    # Reset rotation for a clean transition in local look modes
                    if "look" in camera_modes[camera_mode_idx]:
                        rotation_x = 0.0
                        rotation_y = 0.0
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:  # Scroll Up (Zoom In)
                    if camera_modes[camera_mode_idx] == "orbit":
                        zoom = min(zoom + 0.8, -2.0)
                    else:
                        fov = max(fov - 2.0, 2.0)
                elif event.button == 5:  # Scroll Down (Zoom Out)
                    if camera_modes[camera_mode_idx] == "orbit":
                        zoom = max(zoom - 0.8, -45.0)
                    else:
                        fov = min(fov + 2.0, 75.0)

        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:
            rel_x, rel_y = pygame.mouse.get_rel()
            if camera_modes[camera_mode_idx] == "orbit":
                rotation_y += rel_x * 0.2
                rotation_x += rel_y * 0.2
            else:
                rotation_y += rel_x * 0.2
                rotation_x = max(min(rotation_x + rel_y * 0.2, 89.0), -89.0)
        else:
            pygame.mouse.get_rel()

        target_hit = missile.update()
        if target_hit:
            print("Intercept failed!")
            interceptor.active = False
            interceptor.vel[:] = 0.0
        required_steps = int(config.interceptor_delay_sec / TIME_STEP)
        if config.auto_launch_interceptor and missile.active and len(missile.path) > required_steps and not interceptor_launched:
            interceptor.launch()
            interceptor_launched = True
        if interceptor_launched and missile.active:
            interceptor.update(missile.pos)
            if interceptor.hit:
                missile.active = False

        # Update projection matrix dynamically for zoom/FOV changes
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(fov, display[0] / display[1], 0.001, 100.0)
        glMatrixMode(GL_MODELVIEW)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        camera_mode = camera_modes[camera_mode_idx]
        if camera_mode == "orbit":
            glTranslatef(0.0, 0.0, zoom)
            glRotatef(rotation_x, 1, 0, 0)
            glRotatef(rotation_y, 0, 1, 0)
        else:
            # Identify ground camera station coordinates
            if "interceptor" in camera_mode:
                cam_lat = config.interceptor_start_lat
                cam_lon = config.interceptor_start_lon
                cam_alt = 10.0
            elif "target" in camera_mode:
                cam_lat = config.missile_target_lat
                cam_lon = config.missile_target_lon
                cam_alt = 10.0
            elif "custom" in camera_mode:
                cam_lat = config.custom_cam_lat
                cam_lon = config.custom_cam_lon
                cam_alt = config.custom_cam_altitude_km
            else:  # "missile"
                cam_lat = config.missile_start_lat
                cam_lon = config.missile_start_lon
                cam_alt = 10.0

            # Position camera slightly above surface to avoid near clipping
            eye = lat_lon_to_xyz(cam_lat, cam_lon, radius=EARTH_RADIUS, altitude_km=cam_alt)
            up = eye / np.linalg.norm(eye)

            # Compute local East and North basis vectors at this location
            theta_rad = math.radians(cam_lon)
            east = np.array([-math.sin(theta_rad), 0.0, math.cos(theta_rad)], dtype=float)
            east_norm = np.linalg.norm(east)
            if east_norm > 1e-9:
                east /= east_norm
            north = np.cross(east, up)
            north_norm = np.linalg.norm(north)
            if north_norm > 1e-9:
                north /= north_norm

            if "track" in camera_mode:
                # Automatically track the active threat or interceptor
                if missile.active:
                    center = missile.pos
                elif interceptor.active:
                    center = interceptor.pos
                else:
                    center = lat_lon_to_xyz(config.missile_target_lat, config.missile_target_lon, radius=EARTH_RADIUS)
            else:
                # Look freely with yaw and pitch relative to the local horizon
                yaw_rad = math.radians(rotation_y)
                pitch_rad = math.radians(max(min(rotation_x, 89.0), -89.0))
                
                look_horizontal = math.cos(yaw_rad) * north + math.sin(yaw_rad) * east
                local_look = math.cos(pitch_rad) * look_horizontal + math.sin(pitch_rad) * up
                center = eye + local_look

            gluLookAt(eye[0], eye[1], eye[2], center[0], center[1], center[2], up[0], up[1], up[2])

        draw_sphere(EARTH_RADIUS)
        draw_location_marker(config.missile_start_lat, config.missile_start_lon, (1.0, 0.25, 0.25), altitude_km=config.missile_start_altitude_km, radius_scale=1.05)
        draw_location_marker(config.missile_target_lat, config.missile_target_lon, (1.0, 0.85, 0.15), altitude_km=config.missile_target_altitude_km, radius_scale=1.05)
        draw_location_marker(config.interceptor_start_lat, config.interceptor_start_lon, (0.1, 0.85, 0.65), altitude_km=config.interceptor_start_altitude_km, radius_scale=1.05)
        
        # Render threat paths as tactical overlay (always visible through/over the globe curvature from the ground)
        glDisable(GL_DEPTH_TEST)
        missile.draw()
        interceptor.draw()
        glEnable(GL_DEPTH_TEST)

        # Draw the tactical HUD center mark over the screen
        draw_center_mark(display[0], display[1])

        # Update caption with camera mode status
        mode_str = {
            "orbit": "Orbit View",
            "ground_interceptor_track": "Ground Camera (Intcp Site) - Tracking Missile",
            "ground_interceptor_look": "Ground Camera (Intcp Site) - Looking around",
            "ground_target_track": "Ground Camera (Target Site) - Tracking Missile",
            "ground_target_look": "Ground Camera (Target Site) - Looking around",
            "ground_missile_track": "Ground Camera (Missile Launch) - Tracking",
            "ground_missile_look": "Ground Camera (Missile Launch) - Looking around",
            "ground_custom_track": "Ground Camera (Custom Site) - Tracking Missile",
            "ground_custom_look": "Ground Camera (Custom Site) - Looking around",
        }.get(camera_mode, "Orbit View")
        pygame.display.set_caption(f"3D Global Missile Intercept Simulation | View: {mode_str} | Press 'C' to Cycle | Scroll to Zoom")

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def load_simulation_settings():
    """Loads custom settings from the Tkinter GUI settings file."""
    settings_file = os.path.join(os.path.dirname(__file__), "mslwarntest_settings.json")
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return data


def main():
    data = load_simulation_settings()
    config = SimulationConfig(
        missile_speed=float(data.get("missile_speed", 5.0)) / 1000.0,
        interceptor_speed=float(data.get("interceptor_speed", 7.0)) / 1000.0,
        proportional_gain=float(data.get("proportional_gain", 4.0)),
        auto_launch_interceptor=bool(data.get("auto_launch_interceptor", True)),
        missile_start_lat=float(data.get("missile_start_lat", 39.0)),
        missile_start_lon=float(data.get("missile_start_lon", 125.0)),
        missile_start_altitude_km=float(data.get("missile_start_altitude_km", 0.0)),
        missile_target_lat=float(data.get("missile_target_lat", 38.0)),
        missile_target_lon=float(data.get("missile_target_lon", -77.0)),
        missile_target_altitude_km=float(data.get("missile_target_altitude_km", 0.0)),
        interceptor_start_lat=float(data.get("interceptor_start_lat", 64.0)),
        interceptor_start_lon=float(data.get("interceptor_start_lon", -147.0)),
        interceptor_start_altitude_km=float(data.get("interceptor_start_altitude_km", 0.0)),
        interceptor_delay_sec=float(data.get("interceptor_delay_sec", 3.0)),
        custom_cam_lat=float(data.get("view_center_lat", 38.54)),
        custom_cam_lon=float(data.get("view_center_lon", 100.74)),
        custom_cam_altitude_km=float(data.get("view_altitude_km", 0.5)),
        custom_view_yaw_deg=float(data.get("view_yaw_deg", 169.26)),
        custom_view_pitch_deg=float(data.get("view_pitch_deg", 38.54)),
        missile_loft_factor=float(data.get("simulation_missile_loft_factor", 0.8)),
        missile_hit_radius=float(data.get("simulation_missile_hit_radius", 0.0015)),
        interceptor_hit_radius=float(data.get("simulation_interceptor_hit_radius", 0.003)),
        loft_vis_ratio=float(data.get("simulation_loft_vis_ratio", 1.0)),
    )
    run_simulation(config)


if __name__ == "__main__":
    main()
