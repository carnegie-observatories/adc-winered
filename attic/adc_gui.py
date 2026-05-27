#!/usr/bin/env python3
"""
ADC Control GUI - NiceGUI implementation
Recreates the ADC window from MainMenu.xib
"""

import httpx
from nicegui import ui


class ADCController:
    """Controller class for ADC state and callbacks."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        
        # Telescope values (read-only from TCS)
        self.elevation = 0.0
        self.rotator = 0.0
        
        # Stage 1 - ADC
        self.adc_position = 'Retracted'
        self.prism_a = 0.0
        self.prism_b = 0.0
        self.target_a = 0.0
        self.target_b = 0.0
        self.control_mode = 'Off'
        
        # Stage 2 - Mirror
        self.mirror_position = 'Retracted'
        
        # Status indicators
        self.adc_moving = False
        self.lens_a_moving = False
        self.lens_b_moving = False
        self.mirror_moving = False
        
        # Status colors (True = Online/OK, False = Offline/Error)
        self.adc_in_status = False
        self.adc_out_status = False
        self.mirror_in_status = False
        self.mirror_out_status = False
        
        # Connection status
        self.connected = False
        self.tcs_connected = False
        self.plc_connected = False
        
        # Settings
        self.tcs_poll_interval = 1.0
        self.prism_mode = 0  # 0: Normal, 1: No Dispersion, 2: Inverted
        
        # Input focus tracking
        self.target_a_focused = False
        self.target_b_focused = False
        
        # Run/Park state (derived from control_mode and position)
        self.is_running = False
        
        self.prism_mode_options = {
            0: 'Normal',
            1: 'No Dispersion',
            2: 'Inverted'
        }

    async def fetch_settings(self):
        """Fetch current settings from server."""
        try:
            resp = await self.client.get("/settings")
            if resp.status_code == 200:
                data = resp.json()
                self.tcs_poll_interval = data["tcs_poll_interval"]
                self.prism_mode = data["prism_mode"]
        except httpx.RequestError:
            pass

    async def update_tcs_poll_interval(self):
        """Update TCS poll interval on server."""
        try:
            resp = await self.client.post("/settings/interval", json={
                "interval": self.tcs_poll_interval
            })
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "error":
                    ui.notify(data.get("message", "Error updating interval"), type='negative')
                else:
                    ui.notify(f"TCS poll interval set to {self.tcs_poll_interval:.2f}s", type='positive')
        except httpx.RequestError:
            ui.notify("Connection error", type='negative')

    async def update_prism_mode(self):
        """Update prism mode on server."""
        try:
            resp = await self.client.post("/adc/prism_mode", json={
                "mode": self.prism_mode
            })
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "error":
                    ui.notify(data.get("message", "Error updating prism mode"), type='negative')
                else:
                    mode_name = self.prism_mode_options.get(self.prism_mode, str(self.prism_mode))
                    ui.notify(f"Prism mode set to {mode_name}", type='positive')
        except httpx.RequestError:
            ui.notify("Connection error", type='negative')

    async def fetch_all_status(self):
        """Fetch all status from server."""
        try:
            # Fetch telescope data
            resp = await self.client.get("/telescope")
            if resp.status_code == 200:
                data = resp.json()
                self.elevation = data["elevation"]
                self.rotator = data["rotator"]
            
            # Fetch ADC status
            resp = await self.client.get("/adc/status")
            if resp.status_code == 200:
                data = resp.json()
                self.adc_position = data["position"]
                self.prism_a = data["prism_a"]
                self.prism_b = data["prism_b"]
                # Only update targets if user is not editing them
                if not self.target_a_focused:
                    self.target_a = data["target_a"]
                if not self.target_b_focused:
                    self.target_b = data["target_b"]
                self.control_mode = data["control_mode"]
                self.adc_moving = data["moving"]
                self.lens_a_moving = data["lens_a_moving"]
                self.lens_b_moving = data["lens_b_moving"]
                self.adc_in_status = data["in_status"]
                self.adc_out_status = data["out_status"]
                # Update running state based on position and control mode
                self.is_running = (self.adc_position == 'Inserted' and self.control_mode == 'Auto')
            
            # Fetch mirror status
            resp = await self.client.get("/mirror/status")
            if resp.status_code == 200:
                data = resp.json()
                self.mirror_position = data["position"]
                self.mirror_moving = data["moving"]
                self.mirror_in_status = data["in_status"]
                self.mirror_out_status = data["out_status"]
            
            self.connected = True
        except httpx.RequestError:
            self.connected = False

    async def fetch_health(self):
        """Fetch health status from server."""
        try:
            resp = await self.client.get("/health")
            if resp.status_code == 200:
                data = resp.json()
                self.tcs_connected = data.get("tcs_connected", False)
                self.plc_connected = data.get("plc_connected", False)
        except httpx.RequestError:
            self.tcs_connected = False
            self.plc_connected = False

    async def on_slide_adc(self):
        """Handle ADC slide position change."""
        try:
            await self.client.post("/adc/position", json={"position": self.adc_position})
        except httpx.RequestError:
            pass

    async def on_slide_mirror(self):
        """Handle Mirror slide position change."""
        try:
            await self.client.post("/mirror/position", json={"position": self.mirror_position})
        except httpx.RequestError:
            pass

    async def on_target_a_change(self):
        """Handle Target-A setpoint change (manual mode only)."""
        if self.control_mode != 'Off':
            return
        try:
            await self.client.post("/adc/prism", json={"prism_a": self.target_a})
        except httpx.RequestError:
            pass

    async def on_target_b_change(self):
        """Handle Target-B setpoint change (manual mode only)."""
        if self.control_mode != 'Off':
            return
        try:
            await self.client.post("/adc/prism", json={"prism_b": self.target_b})
        except httpx.RequestError:
            pass

    async def on_control_change(self):
        """Handle control mode change."""
        try:
            await self.client.post("/adc/control", json={"mode": self.control_mode})
        except httpx.RequestError:
            pass

    async def on_run_park_toggle(self):
        """Toggle between Run and Park states."""
        try:
            if self.is_running:
                # Park: set control to Off, then retract
                await self.client.post("/adc/control", json={"mode": "Off"})
                await self.client.post("/adc/position", json={"position": "Retracted"})
                self.control_mode = 'Off'
                self.adc_position = 'Retracted'
                self.is_running = False
            else:
                # Run: insert and set control to Auto
                await self.client.post("/adc/position", json={"position": "Inserted"})
                await self.client.post("/adc/control", json={"mode": "Auto"})
                self.adc_position = 'Inserted'
                self.control_mode = 'Auto'
                self.is_running = True
        except httpx.RequestError:
            pass


def create_status_indicator(controller, attr: str) -> ui.element:
    """Create a colored status indicator that binds to controller attribute."""
    indicator = ui.element('div').classes('rounded').style(
        'width: 20px; height: 20px; border: 1px solid #888;'
    )
    
    def update_color():
        active = getattr(controller, attr)
        color = '#00ff00' if active else '#0000ff'
        indicator.style(f'width: 20px; height: 20px; background-color: {color}; border: 1px solid #888;')
    
    indicator.bind_visibility_from(controller, attr, backward=lambda _: True)  # Forces refresh
    ui.timer(0.5, update_color)  # Update color periodically
    return indicator


def create_moving_indicator(controller, attr: str) -> ui.element:
    """Create an LED-like indicator for movement status (yellow=moving, dark=idle)."""
    indicator = ui.element('div').classes('rounded-full').style(
        'width: 12px; height: 12px; border: 1px solid #555;'
    )
    
    def update_color():
        moving = getattr(controller, attr)
        if moving:
            # Yellow/amber glow when moving
            indicator.style('width: 12px; height: 12px; background-color: #ffcc00; border: 1px solid #555; box-shadow: 0 0 6px #ffcc00;')
        else:
            # Dark/off when idle
            indicator.style('width: 12px; height: 12px; background-color: #333; border: 1px solid #555;')
    
    ui.timer(0.3, update_color)
    return indicator


def create_adc_window_content(controller: ADCController):
    """Create the main ADC control window content."""
    with ui.card().style('padding: 12px;'):
        ui.label('ADC').classes('text-xl font-bold mb-2')
        
        # === Telescope Box ===
        with ui.card().classes('w-full mb-2').style('border: 1px solid #ccc;'):
            ui.label('Telescope').classes('text-sm font-semibold')
            
            with ui.row().classes('items-center gap-4 mt-2'):
                # Elevation (readonly)
                ui.label('Elevation')
                ui.label().bind_text_from(controller, 'elevation', backward=lambda v: f'{v:.2f}').classes('w-20 text-right font-mono')
                
                # Rotator (readonly)
                ui.label('Rotator')
                ui.label().bind_text_from(controller, 'rotator', backward=lambda v: f'{v:.2f}').classes('w-20 text-right font-mono')
        
        # === Stage 1 - ADC Box ===
        with ui.card().classes('w-full mb-2').style('border: 1px solid #ccc;'):
            ui.label('Stage 1 - ADC').classes('text-sm font-semibold')
            
            # Top row: ADC position and status indicators
            with ui.row().classes('items-center gap-2 mt-2'):
                # ADC position dropdown
                ui.select(
                    options=['Retracted', 'Inserted'],
                    value=controller.adc_position,
                    on_change=controller.on_slide_adc
                ).bind_value(controller, 'adc_position')
                
                ui.space()
                
                # Status indicators
                ui.label('Out').classes('text-xs')
                create_status_indicator(controller, 'adc_out_status')
                
                ui.label('In').classes('text-xs')
                create_status_indicator(controller, 'adc_in_status')
                
                ui.space()

                # Control dropdown
                ui.label('Control')
                ui.select(
                    options=['Off', 'Auto'],
                    value=controller.control_mode,
                    on_change=controller.on_control_change
                ).bind_value(controller, 'control_mode')
                
                # Run/Park button
                run_park_btn = ui.button('Run', on_click=controller.on_run_park_toggle).props('dense')
                
                def update_run_park_btn():
                    if controller.is_running:
                        run_park_btn.text = 'Park'
                        run_park_btn.style('background-color: #dc2626 !important;')  # red
                    else:
                        run_park_btn.text = 'Run'
                        run_park_btn.style('background-color: #16a34a !important;')  # green
                
                ui.timer(0.5, update_run_park_btn)
            
            # Prism-A row
            with ui.row().classes('items-center gap-2 mt-2'):
                ui.label('Prism-A')
                create_moving_indicator(controller, 'lens_a_moving')
                ui.label().bind_text_from(controller, 'prism_a', backward=lambda v: f'{v:.2f}').classes('w-20 text-right font-mono')
                
                ui.space()
                
                # Target A (editable in OFF mode)
                ui.label('Target')
                target_a_input = ui.number(
                    value=controller.target_a,
                    format='%.2f',
                    step=1.0
                ).bind_value(controller, 'target_a').props('dense').classes('w-24')
                target_a_input.on('focus', lambda: setattr(controller, 'target_a_focused', True))
                
                async def on_target_a_blur():
                    controller.target_a_focused = False
                    await controller.on_target_a_change()
                target_a_input.on('blur', on_target_a_blur)
                
                def update_target_a_enabled():
                    if controller.control_mode == 'Off':
                        target_a_input.enable()
                    else:
                        target_a_input.disable()
                ui.timer(0.5, update_target_a_enabled)
            
            # Prism-B row
            with ui.row().classes('items-center gap-2 mt-1'):
                ui.label('Prism-B')
                create_moving_indicator(controller, 'lens_b_moving')
                ui.label().bind_text_from(controller, 'prism_b', backward=lambda v: f'{v:.2f}').classes('w-20 text-right font-mono')
                
                ui.space()
                
                # Target B (editable in OFF mode)
                ui.label('Target')
                target_b_input = ui.number(
                    value=controller.target_b,
                    format='%.2f',
                    step=1.0
                ).bind_value(controller, 'target_b').props('dense').classes('w-24')
                target_b_input.on('focus', lambda: setattr(controller, 'target_b_focused', True))
                
                async def on_target_b_blur():
                    controller.target_b_focused = False
                    await controller.on_target_b_change()
                target_b_input.on('blur', on_target_b_blur)
                
                def update_target_b_enabled():
                    if controller.control_mode == 'Off':
                        target_b_input.enable()
                    else:
                        target_b_input.disable()
                ui.timer(0.5, update_target_b_enabled)
        
        # === Stage 2 - Mirror Box ===
        with ui.card().classes('w-full').style('border: 1px solid #ccc;'):
            ui.label('Stage 2 - Mirror').classes('text-sm font-semibold')
            
            with ui.row().classes('items-center gap-2 mt-2'):
                # Mirror position dropdown
                ui.select(
                    options=['Retracted', 'Inserted'],
                    value=controller.mirror_position,
                    on_change=controller.on_slide_mirror
                ).bind_value(controller, 'mirror_position')
                
                ui.space()
                
                # Status indicators
                ui.label('Out').classes('text-xs')
                create_status_indicator(controller, 'mirror_out_status')
                
                ui.label('In').classes('text-xs')
                create_status_indicator(controller, 'mirror_in_status')


def create_settings_page(controller: ADCController):
    """Create the settings page content."""
    with ui.card().style('padding: 20px; min-width: 400px;'):
        ui.label('Settings').classes('text-xl font-bold mb-4')
        
        # TCS Poll Interval
        with ui.card().classes('w-full mb-4').style('border: 1px solid #ccc;'):
            ui.label('TCS Polling').classes('text-sm font-semibold')
            
            with ui.row().classes('items-center gap-4 mt-2'):
                ui.label('Interval (seconds)')
                ui.number(
                    value=controller.tcs_poll_interval,
                    format='%.2f',
                    min=0.1,
                    max=10.0,
                    step=0.1
                ).bind_value(controller, 'tcs_poll_interval').props('dense')
                
                ui.button('Apply', on_click=controller.update_tcs_poll_interval).props('dense')
        
        # Prism Mode
        with ui.card().classes('w-full').style('border: 1px solid #ccc;'):
            ui.label('Prism Control').classes('text-sm font-semibold')
            
            with ui.row().classes('items-center gap-4 mt-2'):
                ui.label('Mode')
                ui.select(
                    options={0: 'Normal', 1: 'No Dispersion', 2: 'Inverted'},
                    value=controller.prism_mode,
                    on_change=controller.update_prism_mode
                ).bind_value(controller, 'prism_mode').props('dense')
            
            with ui.column().classes('mt-2 text-xs text-gray-400'):
                ui.label('Normal: Default dispersion correction')
                ui.label('No Dispersion: Prisms parallel (no correction)')
                ui.label('Inverted: Reversed dispersion correction')


# Store controller globally for multi-page access
_controller: ADCController | None = None


def create_health_status(controller: ADCController):
    """Create health status chips that update based on connection state."""
    with ui.row().classes('gap-2'):
        # TCS status chip
        tcs_chip = ui.chip('TCS', icon='sensors')
        
        def update_tcs_chip():
            if controller.tcs_connected:
                tcs_chip.set_background_color('green')
            else:
                tcs_chip.set_background_color('red')
        
        ui.timer(0.5, update_tcs_chip)
        
        # PLC status chip
        plc_chip = ui.chip('PLC', icon='memory')
        
        def update_plc_chip():
            if controller.plc_connected:
                plc_chip.set_background_color('green')
            else:
                plc_chip.set_background_color('red')
        
        ui.timer(0.5, update_plc_chip)


@ui.page('/')
async def main_page():
    """Main page with ADC control window."""
    global _controller
    ui.dark_mode(True)
    
    _controller = ADCController()
    
    with ui.header().classes('items-center justify-between'):
        ui.label('ADC Control').classes('text-lg font-bold')
        create_health_status(_controller)
        with ui.row():
            ui.link('Control', '/').classes('text-white mx-2')
            ui.link('Settings', '/settings').classes('text-white mx-2')
    
    with ui.column().classes('items-center p-4'):
        create_adc_window_content(_controller)
    
    # Initial fetch
    await _controller.fetch_all_status()
    await _controller.fetch_health()
    
    # Poll server every 2 seconds
    async def poll_status():
        await _controller.fetch_all_status()
        await _controller.fetch_health()
    
    ui.timer(2.0, poll_status)


@ui.page('/settings')
async def settings_page():
    """Settings page for ADC configuration."""
    ui.dark_mode(True)
    
    with ui.header().classes('items-center justify-between'):
        ui.label('ADC Control').classes('text-lg font-bold')
        with ui.row():
            ui.link('Control', '/').classes('text-white mx-2')
            ui.link('Settings', '/settings').classes('text-white mx-2')
    
    controller = ADCController()
    
    with ui.column().classes('items-center p-4'):
        create_settings_page(controller)
    
    # Fetch current settings
    await controller.fetch_settings()


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='ADC Control', port=8080, reload=True)



