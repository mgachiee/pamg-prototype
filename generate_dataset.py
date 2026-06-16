import os
import random
import mido
import math
from typing import Dict, List, Tuple

from src.core.configs import *
from src.modules.percussion_agent import PercussionAgent
from src.modules.melody_agent import MelodyAgent
from src.modules.harmony_agent import HarmonyAgent
from src.modules.orchestrator_agent import OrchestratorAgent
from src.core.seeded_phrase_generator import SeededPhraseGenerator
from src.core.midi_events import normalize_event

def generate_dataset():
    output_dir = "dataset"
    os.makedirs(output_dir, exist_ok=True)
    
    presets = {
        "A": PRESET_A,
        "B": PRESET_B,
        "C": PRESET_C,
        "D": PRESET_D
    }
    
    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    grain = 4
    loop_size = 4
    target_duration_sec = 120.0  # 2 minutes
    ticks_per_beat = 480
    ticks_per_pulse = ticks_per_beat // grain  # 16th note = 120 ticks at grain 4
    
    for preset_name, preset in presets.items():
        print(f"Generating 25 files for Preset {preset_name} (Quadrant Mapping)...")
        
        for file_idx in range(1, 26):
            # 1. Randomize BPM based on preset tension/energy
            if preset_name in ("B", "D"): # High Energy / High Arousal
                bpm = random.randint(110, 150)
            else: # Low Energy / Calm / Sad
                bpm = random.randint(80, 105)
            
            base_seed = random.randint(1, 999999)
            
            # Calculate required loops for 2 minutes
            seconds_per_loop = (60.0 / bpm) * loop_size
            num_loops = math.ceil(target_duration_sec / seconds_per_loop)
            total_ticks_count = num_loops * loop_size * grain
            
            pulse_duration_sec = 60.0 / (bpm * grain)
            
            # 2. Initialize Agent Network
            percussion_agent = PercussionAgent(loop_size=loop_size, grain=grain)
            melody_agent = MelodyAgent(movement="odd", loop_size=loop_size, grain=grain)
            harmony_agent = HarmonyAgent(loop_size=loop_size, grain=grain)
            
            # Orchestral Instrumentation (GM Mapping)
            orchestrator_agent = OrchestratorAgent(
                melody_channels=[0, 1],       # Ch 1 (Violin), Ch 2 (Flute)
                harmony_channels=[2, 3, 4],    # Ch 3 (Piano), Ch 4 (Strings), Ch 5 (Bass)
                harmony_layer_weights=[1.0, 1.0, 1.0], 
                melody_range=MELODY_RANGE,
                harmony_range=HARMONY_RANGE,
                harmony_programs=[0, 48, 32], # Piano, Strings, Bass
                melody_program=40,            # Violin
                harmony_layer_mode="deterministic"
            )
            
            orchestrator_agent.update_params(
                family_ranges={
                    "violin": (55, 100),
                    "flute": (60, 96),
                    "piano": (21, 108),
                    "strings": (40, 84),
                    "bass": (24, 48)
                },
                channel_families={0: "violin", 1: "flute", 2: "piano", 3: "strings", 4: "bass"}
            )
            
            spg = SeededPhraseGenerator(base_seed=base_seed)
            _spg_prev_seed = spg.current_seed
            last_chord_pool = harmony_agent.get_chord_pool()
            
            # Event collection (channel -> List[absolute_tick, message])
            track_events: Dict[int, List[Tuple[int, mido.Message]]] = {ch: [] for ch in range(16)}
            
            # Initial setup: Programs
            track_events[0].append((0, mido.Message('program_change', channel=0, program=40))) # Violin
            track_events[1].append((0, mido.Message('program_change', channel=1, program=73))) # Flute
            track_events[2].append((0, mido.Message('program_change', channel=2, program=0)))  # Piano
            track_events[3].append((0, mido.Message('program_change', channel=3, program=48))) # Strings
            track_events[4].append((0, mido.Message('program_change', channel=4, program=32))) # Bass
            
            # 3. Offline Tick Loop
            phrase_length = max(1, int(round(preset.seeded_phrase_length)))
            
            for tick in range(total_ticks_count):
                local_index = tick % (loop_size * grain)
                loop_index = tick // (loop_size * grain)
                beat_index = local_index // grain
                measure_index = beat_index % loop_size
                subdivision = local_index % grain
                
                phrase_start = subdivision == 0 and (measure_index % phrase_length) == 0
                
                # Update agent parameters at phrase boundaries
                if tick == 0 or phrase_start:
                    melody_agent.update_params(
                        max_step=max(1, int(round(preset.melody_max_step))),
                        pitch_range=(int(preset.melody_pitch_low), int(preset.melody_pitch_high)),
                        syncopation_probability=float(preset.melody_syncopation),
                        accent_probability=float(preset.melody_accent),
                        ratchet_probability=float(preset.melody_ratchet_probability),
                    )
                    orchestrator_agent.update_params(
                        melody_range=(int(preset.melody_pitch_low), int(preset.melody_pitch_high)),
                        harmony_range=(int(preset.harmony_pitch_low), int(preset.harmony_pitch_high)),
                        harmony_layer_weights=list(preset.harmony_layer_weights),
                    )
                    percussion_agent.update_params(
                        kick_sub_prob=1.0 - float(preset.drum_kick_probability),
                        ghost_kick_prob=float(preset.drum_ghost_kick_probability),
                        snare_sub_prob=1.0 - float(preset.drum_snare_probability),
                        hat_open_prob=float(preset.drum_hat_open_probability),
                        hat_closed_prob=float(preset.drum_hat_closed_probability),
                        hat_ratchet_prob=float(preset.drum_ratchet_probability),
                    )
                    harmony_agent.update_params(
                        tension=float(preset.harmony_tension),
                        chord_complexity=float(preset.harmony_chord_complexity),
                        chord_change_probability=float(preset.harmony_chord_change_probability),
                        harmony_add_probability=float(preset.harmony_add_probability),
                        harmony_sub_probability=float(preset.harmony_sub_probability),
                        harmony_accent_probability=float(preset.harmony_accent_probability),
                        scale_mode=preset.scale_mode,
                    )
                
                if phrase_start:
                    melody_agent.on_phrase_start()
                    orchestrator_agent.on_phrase_start()
                    
                if local_index == 0:
                    melody_agent.on_loop_start(loop_index)
                    percussion_agent.on_loop_start(loop_index)
                    accent_list = melody_agent.get_accent_list()
                    harmony_agent.notify_accents(accent_list)
                    percussion_agent.notify_accents(accent_list)
                
                # Chord and Seed logic
                current_chord = harmony_agent.get_current_chord(measure_index=measure_index)
                if subdivision == 0:
                    new_seed = spg.process_chord_change(harmony_agent.get_chord_pool(), phrase_length)
                    if new_seed != _spg_prev_seed:
                        melody_agent.update_params(seed=new_seed)
                        percussion_agent.update_params(seed=new_seed)
                        harmony_agent.update_params(seed=new_seed)
                        _spg_prev_seed = new_seed
                        
                current_chord_pool = harmony_agent.get_chord_pool()
                if current_chord_pool != last_chord_pool:
                    percussion_agent.notify_chord_change(current_chord_pool)
                    last_chord_pool = current_chord_pool
                
                # Generate Hits
                drum_hits = percussion_agent.process_tick(index=local_index)
                harmony_hits = harmony_agent.process_tick(index=local_index, pulse_duration=pulse_duration_sec)
                melody_hits = melody_agent.process_tick(index=local_index, current_chord=current_chord, pulse_duration=pulse_duration_sec)
                orchestrated_hits = orchestrator_agent.process_tick(melody_hits, harmony_hits)
                
                # Consume CC changes
                for ch, cc, val in orchestrator_agent.consume_cc_changes():
                    track_events[ch].append((tick * ticks_per_pulse, mido.Message('control_change', channel=ch, control=cc, value=val)))
                
                # Process Note Events
                def process_events(hits, default_ch):
                    abs_tick_start = tick * ticks_per_pulse
                    for hit in hits:
                        ev = normalize_event(hit=hit, default_channel=default_ch, default_duration=pulse_duration_sec * 0.9)
                        if not ev: continue
                        
                        dur_ticks = int((ev.duration / pulse_duration_sec) * ticks_per_pulse)
                        
                        if ev.is_ratchet:
                            sub_ticks = dur_ticks // max(1, ev.ratchet_count)
                            for r in range(ev.ratchet_count):
                                r_start = abs_tick_start + r * sub_ticks
                                r_end = r_start + int(sub_ticks * 0.6)
                                track_events[ev.channel].append((r_start, mido.Message('note_on', channel=ev.channel, note=ev.note, velocity=ev.velocity)))
                                track_events[ev.channel].append((r_end, mido.Message('note_off', channel=ev.channel, note=ev.note, velocity=ev.velocity)))
                        else:
                            track_events[ev.channel].append((abs_tick_start, mido.Message('note_on', channel=ev.channel, note=ev.note, velocity=ev.velocity)))
                            track_events[ev.channel].append((abs_tick_start + dur_ticks, mido.Message('note_off', channel=ev.channel, note=ev.note, velocity=ev.velocity)))

                process_events(orchestrated_hits, 0)
                process_events(drum_hits, 9)

            # 4. Save MIDI File
            mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
            # Meta Track (Tempo)
            meta_track = mido.MidiTrack()
            mid.tracks.append(meta_track)
            meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
            meta_track.append(mido.MetaMessage('track_name', name=f"Preset {preset_name} - {bpm}BPM", time=0))
            
            for ch, events in track_events.items():
                if not events: continue
                
                track = mido.MidiTrack()
                mid.tracks.append(track)
                
                # Sort absolute times (NoteOff must come before NoteOn at same tick)
                def sort_key(e):
                    msg = e[1]
                    prio = 1
                    if msg.type == 'note_off' or msg.type == 'control_change': prio = 0
                    elif msg.type == 'program_change': prio = -1
                    return (e[0], prio)
                
                events.sort(key=sort_key)
                
                last_t = 0
                for abs_t, msg in events:
                    delta = abs_t - last_t
                    msg.time = delta
                    track.append(msg)
                    last_t = abs_t
            
            filename = f"Preset_{preset_name}_{file_idx:02d}.mid"
            mid.save(os.path.join(output_dir, filename))
            
    print(f"\nSuccessfully generated 100 MIDI files in the '{output_dir}/' directory.")

if __name__ == "__main__":
    generate_dataset()
