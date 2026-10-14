> **Compiler's note:** The source PDF extraction interleaved this two-column paper's text out of true reading order (left-column-then-right-column-then-next-page). This file restores correct sequence without altering, omitting, or paraphrasing any wording. Two extraction artifacts were resolved in restoring order: (1) a sentence fragment on pp.67–68 that was duplicated by the extractor is presented once, in its correct single location; (2) Figures 6 and 7 (left column, p.70) are placed before the Discussion text that follows them (right column, p.70), since the raw extraction had reversed that pair. Figure/diagram *images* are not reproduced here — only their printed captions — since this is a text-sequencing task, not a layout reproduction. This copy is made under the paper's own stated permission (reproduced in full below) for personal/non-commercial use, with the required notice and citation retained.

---

# A Progressive-Adaptive Music Generator (PAMG)

## An Approach to Interactive Procedural Music for Videogames

**Alvaro Eduardo Lopez Duarte**
University of California, Riverside, USA
Riverside, USA
alvaro.lopez@ucr.edu

### Abstract

Procedural music generation in video game is rarely used in development despite its potential support for interactive narratives, and falls behind broadly-used procedural methods like graphic management. Currently, developers rely on pre-produced audio sequences, focusing on sound quality while balancing storage and variety. Techniques like layering and re-sequencing are standard through sound design platforms like FMOD and Wwise, allowing adaptation and interactivity in gameplay. However, this can lead to repetitive audio, which becomes particularly noticeable in extended gaming sessions, diminishing the impact of musical storytelling.

This study introduces the Progressive Adaptive Music Generator (PAMG), an algorithmic system that generates continuous music streams based on gameplay variables, seamlessly transitioning between moods, styles, and tension levels. It includes motivation, theoretical framework in the field of generative music, overview of the system structure, and a preliminary implementation test involving a Trial Game that compares conventional implementation with PAMG. In the discussion section, it addresses test results and issues, and future work. The study reveals a preference for PAMG's music over traditional methods in certain aspects, although results are not conclusive.

**CCS Concepts:** • Computing methodologies → Modeling methodologies; • Applied computing → Sound and music computing.

**Keywords:** AI Music, Game Music, Procedural Music

### ACM Reference Format

Alvaro Eduardo Lopez Duarte. 2024. A Progressive-Adaptive Music Generator (PAMG): An Approach to Interactive Procedural Music for Videogames. In *Proceedings of the 12th ACM SIGPLAN International Workshop on Functional Art, Music, Modelling, and Design (FARM '24), September 2, 2024, Milan, Italy.* ACM, New York, NY, USA, 8 pages. https://doi.org/10.1145/3677996.3678291

### Publication notice

Permission to make digital or hard copies of all or part of this work for personal or classroom use is granted without fee provided that copies are not made or distributed for profit or commercial advantage and that copies bear this notice and the full citation on the first page. Copyrights for components of this work owned by others than the author(s) must be honored. Abstracting with credit is permitted. To copy otherwise, or republish, to post on servers or to redistribute to lists, requires prior specific permission and/or a fee. Request permissions from permissions@acm.org.

*FARM '24, September 2, 2024, Milan, Italy*
© 2024 Copyright held by the owner/author(s). Publication rights licensed to ACM.
ACM ISBN 979-8-4007-1099-5/24/09
https://doi.org/10.1145/3677996.3678291

---

## 1 Introduction

In game development, elements like characters, environments, and events are algorithmically linked through gameplay variables. Real-time interactions between light, textures, and colors determine rendering. Such realism enhances storytelling, narrative immersion, and potentially extends gameplay. From a player's perspective, gameplay combines all elements to create an immersive experience. Engagement hinges on a mix of surprise, satisfaction, and challenge [1], requiring varied emotional support from music. Current technologies offer interactive solutions based on audio clips that use variables to layer, re-sequence, and remix material which has supported transitions and immersive player experiences. Real-time music generation, compared to longer audio segments, is believed to offer greater responsiveness, much like smaller buffer sizes reduce latency in digital audio. Note-sized musical elements potentially provide deeper adaptability and variety, tightly responding to game states, actions, and events. Unlike machine learning approaches requiring extensive data sets, PAMG utilizes a multidimensional algorithmic music-feature setup that responds in real time to gameplay variables, making it less resource intensive and providing a wider and more direct control over known musical characteristics. This project explores algorithmic composition through the design and demonstration of PAMG for multi-linear, real-time music generation. It involves the translation of compositional concepts into logical structures and the design of parameter input/output for interactive, reactive music creation. Building upon theoretical roots and existing methods in algorithmic composition, it assesses their applicability and modifications. The project features a gameplay experiment to test PAMG's real-time control against traditional clip-based implementation (CBI) of music, followed by data analysis, identification of limitations, and future research directions. Testing includes the design and development of the Trial Game in which participants assess PAMG's performance against CBI.

---

## 2 The Field of Algorithmic Generative Music

This overview contextualizes the PAMG design within the broader field of algorithmic composition, tracing its inspiration from general music generation concepts and seminal works to specialized generative adaptive music for video games. For comprehensive historical model survey refer to [40] and [65].

### 2.1 Algorithmic Composition in Connection with PAMG

Algorithmic composition, a methodical instruction sequence for problem-solving, has been instrumental in music creation pre-dating computers [38]. Cope's Experiments in Musical Intelligence [9] and Hiller and Isaacson's Illiac Suite [21], employing computational models with Markov chains [41], are seminal works. While these models use numerical symbols for note representation, akin to PAMG, their approach differs: EMI transforms existing music, and Hiller and Isaacson apply Markov models for feature analysis [2]. In contrast, PAMG generates music using measurable parameters, aligning with knowledge-based systems [42] that follow explicit rules for aesthetic consistency. PAMG's structures are akin to grammars, extensively used in harmonic progression construction [8, 9, 54], a distinct approach within algorithmic composition.

#### 2.1.1 Multi-Agent Systems (MAS)

MAS, known for distributed autonomy and perceptual-action capabilities [56], mirror musical ensembles in their coordination of independent entities. PAMG exemplifies this by utilizing agents responsible for creating distinct musical features like melody, harmony, rhythm, and orchestration, functioning within an ensemble-like network with a structured I/O distribution for algorithmic communication.

#### 2.1.2 Melody Creation and Accents

Initiating with a clock-triggered pseudo-random number generator (PRNG) [36], PAMG generates melodic content via seeding, a method widely used in stochastic processes and Markov chains [3]. Unlike Markov chains that require statistical inputs, PAMG opts for seeded random walk algorithms for melody and sequence generation, offering potential for stylistic replication enhancements. In PAMG, melodic accents, characterized by perceived importance due to factors like sound level and timing variations [58], are achieved by offsetting velocity parameters. These accents are aligned with beats, including delayed or anticipated ones (syncopation), constructing the rhythmic structure of the main melody. Additionally, the pattern is applied to pitch-contour nodes in the "dcontour" mode (a mode that uses random walk to create melody contour), accommodating listener expectations of periodicity related to meter.

#### 2.1.3 Tension, Complexity and Progression

PAMG's design prioritizes progressive transitions from simple to complex music, guided by quantized tension and complexity within Western tonal harmony [5], aligning with most commercial game music's incidental style. Key literary influences are outlined next:

Tension: Efforts to quantify musical tension reveal significant challenges, lacking a universal definition [50]. Tension in music psychology is often linked to expectations of form's conclusion or continuation [16, 22]. Tonal harmony, central to these discussions, associates tension with dualities like stability/instability and consonance/dissonance [33]. Tonal progressions, characterized by rising stress towards climaxes followed by resolution, travel within tonal space [29, 39]. Lerdahl's "tonal pitch space" [31] calculates psychological distances in music, aligning with GTTM's principles. PAMG incorporates these concepts, progressively by adding pitches across 12 levels per chord, producing increased tension. This pitch sequence mirrors historical music periods use of dissonance [10, 25] and is crafted using spectral distance-based perceptual affinities [19, 43], varied by chord function within progressions [28].

Progression Complexity: Complexity in Music Information Retrieval (MIR) often relates to cultural music evolution, preferences, and arousal [20, 63]. In tonal harmony, factors like harmonic rhythm, dissonance, and evolution define complexity [57]. PAMG's network, inspired by David Cope's use of an Augmented Transition Network (ATN), a generative-grammars approach for musical concatenation [9], manages transitions between chord levels. Unlike Cope's method, which relies on learned segments for transitions, PAMG uses Western tonal system-based chord transition probabilities [10] without pre-composed patterns, a similar approach to Tymoczko's firs-order properties on progressions and functional harmony [62]. These generative grammars handle harmonies for chords and melodic tonal grids.

Temporal Complexity: Temporal pattern perception in music is linked to an internal hierarchical clock, which adapts based on the sequence and accented events [47, 58]. [53] suggest a complexity score for this clock, favoring syncopated patterns. [32] present a hierarchical complexity framework based on cognitive segmentation of musical material. Patterns with more sub-symmetries are deemed simpler [61], while measures like the pairwise variability index [60] and Keith's complexity measure [27] link rhythmic complexity to metric grouping. In PAMG's rhythm generation, the simplest pattern is one sub-symmetry per beat. Complexity increases by progressively displacing onsets, with the direction of displacement and onset choice being crucial. Alternating directions and dividing pulses into even and odd for anticipation/delay avoids simplification. As structures of 2 are less complex than those of 3 [18], the PAMG model prefers half-pulse (8th note) displacements over quarter-pulse (16th note). The resulting displaced pattern forms the base accent structure, akin to terminal branches in Lerdahl and Jackendoff's tree structures.

Algorithmic Orchestration: Computer-aided orchestration focuses on symbolic and sample-based methods [4]. Sample-based approaches gather timbral data from audio samples to construct instrument combinations meeting perceptual criteria [13, 48]. While playability is key in algorithmic composition [7], it's treated as a constraint in machine performance contexts [30]. In PAMG's orchestration agent, tasks include setting instrument range constraints, recombining instruments, and harmonizing with the melody agent's output. Basic orchestral functions, like spacing in lower registers and texture management, are handled by the source agent [14]. The design, currently limited to full-range instrument families, aims for modular expansion to accommodate virtual instruments for style diversification.

### 2.2 Adaptive-Generative Music for Videogames

Music significantly enhances immersion in media, particularly in video games, by focusing attention and reinforcing goal-oriented actions [12, 24, 26, 68]. It supports emotions, plot changes, environmental mood, pacing, aesthetic consistency, and thematic unity [64], with adaptability to multi-linear narratives boosting immersion and engagement [17, 55, 66]. Adaptive, interactive, or dynamic music, crucial in multi-linear narratives, involves music alteration based on control inputs [11, 23, 34, 46, 52]. Collins [6] defines procedural composition as controlled, rule-based, real-time evolution, echoing adaptability. Procedural content generation in games, creating content with minimal user input, also adapts music [59]. Generative music, described as ever-changing by Brian Eno, divides into Linguistic/Structural, Interactive/Behavioral, Creative/Procedural, and Biological/Emergent categories [32, 49, 67, 69]. PAMG incorporates these, generating music without pre-existing material and using algorithms configured by users. It employs non-seeded pseudo-random number generators for variance, suggesting a biological/emergent aspect, though deterministic in nature. Plut et al. [46] define generative music in games as systemically autonomous from game logic, a framework applied to PAMG. The field of generative adaptive systems in video games is expanding [23, 44], with a comprehensive list of examples provided in [45].

---

## 3 System Design

The series of figures shown in this document (Figures 1 to 7) explain the system using custom flow diagrams. Algorithms and processes are boxes with input on top and output below. Their input parameters are shown in an enclosed bold box. Processed data accessible at several points in the system by the agents is shown in ovals. Dashed boxes show process

> **Figure 1. System overview.** *(diagram image not reproduced here)* The flow starts with "Play/Stop" that activates the **1. Clock** which generates a time grid for events, constituting the playback algorithm's foundation. It creates a loop of indexed pulses, setting the minimum onset. Parameters include Tempo, Size, and Grain. Clock events are sent to the agent network

---

## 4 Discussion

To test PAMG, a first person shooter The Trial Game was designed. Then, setting up a Clip-Based Implementation (CBI) that employs conventional methods and software (Audiokinetic's Wwise) for game music, and that provides similar interactive properties as PAMG proved to be more time-consuming and offered less interpolation granularity. To establish a fair comparison, CBI design also employed recordings from PAMG to use the same stylistic and instrumental properties. This secures comparison between implementation results such as interactive capabilities and not music quality or audio. PAMG simplifies transitions through variable assignments and preset interpolations, whereas CBI demands extensive design and testing of numerous transition rules. The preliminary test intended to compare CBI and the real-time music generation of PAMG from the player's experience. The primary question is: "How does PAMG's music influence the gameplay experience compared to the pre-recorded-music in CBI?".

> **Figure 2. Melody Agent (MA):** *(diagram image not reproduced here)* **Rhythm Generation** constructs a list of onsets based on beats and syncopates them using parameters like move even/odd and motion value. Additionally, motion patterns are shared with the other agents to emphasise the melody accents completely or partialy. **Velocity Generation** assigns velocities to onsets using a random-walk sequence, with accents on syncopated onsets. **Pitch Generation** utilizes 'drunk' and 'drunk-contour' modes for real-time pitch assignment, with parameters for step, range, and non-repetition. **Transposition and Harmony Filter** adjust pitch values according to melody shape and chord progressions sent by the Harmony Agent. **Shape Melody** modifies a long term shape through transposition over time using using the parameters depth and length. **Change Algorithm** analyzes previous pitches to adjust transposition and phrase structures. **MIDI Event Construction** combines rhythm, velocity, and pitch data to create MIDI event streams to be sent to the Orchestration Agent. It appears as a MIDI output in the three main agents.

> **Figure 3. Harmony Agent (HA).** *(diagram image not reproduced here)* Similar *Rhythm Generation* to MA, with accent/beat following and additive/subtractive filling. *Velocity Generation* emphasizes chord onsets depending on the main accent list provided by MA. *Harmony Sequence Generation* includes the *Switch* mechanism, the *Chord* structures available in a dictionary, and *Progression Selector* that manages harmonic content and complexity. A *Post Filter* enables filtering to switch rapidly to a new pitch sub-set. *Chord Builder* and *Arpeggiator* construct harmonies for playback. *Harmony Change* adjusts parameters based on chord progressions such as modulations and changes in rhythmic patterns.

The dependent variables were player assessments of engagement, emotional response, immersion, and curiosity for CBI and PAMG in a questionnaire, rated as clearly more/better, slightly more/better, or no significant difference. 18 participants were split equally into two groups: CBI-first and PAMG-first. After playing for 10-20 minutes the game with each implementation, they rated gameplay experience. In general, results suggested that PAMG had a slightly higher impact on participants than CBI with a punctuation in favor of PAMG of 184 (128 slightly + 56 clearly more/better) and 134 in favor of CBI (99 slightly + 35 clearly more/better). Participants who played either CBI or PAMG second tended to rate that model slightly higher. For instance, CBI slightly better increased from 16% when played first to 32% when played second. However, in both groups, PAMG clearly better consistently outscored CBI clearly better (15% vs. 8%, and 12% vs. 9%, respectively). An ANOVA with an alpha of .05 was used to test two hypotheses: H1, a significant model preference (CBI or PAMG), and H2, the influence of play order (CBI-first or PAMG-first) on preference.

> **Figure 4. Percussion Agent (PA):** *(diagram image not reproduced here)* *Rhythm Generation* acts similar to the equivalent in MA and HA but by each percussion instrument. *Velocity Generation* accentuates specific percussion onsets. *Ratchet* decides when and how fill-in rhythmic repetitions appear. *Change* aligns percussion with chord changes.

The analysis showed no significant overall preference for either model, F(1, 17) = 2.46, p = .13, slightly favoring PAMG. Additionally, no significant differences emerged in model preference between the two groups, indicated by between-subjects effects, F(1, 16) = 1.82, p = .19, and within-subjects effects, F(1, 16) = 2.35, p = .14. Votes for PAMG vs. CBI per group revealed a marginally significant effect of group interaction, F(1,16) = 3.79, p = .06, suggesting a skewed preference towards the second model. This tilt may be explained by the priming effect. Initially focused on objectives and mechanics, players gradually expand their attention to elements like background music, enhancing music assessment reliability over time.

The test issues may be solved with a larger sample, a priming gameplay without music, and a longer test. The short gameplay duration in our study limits the assessment of liking versus repeated exposure effects [37, 51]. Players encountered a musical theme 4 to 10 times, possibly experiencing only the initial phase of increased liking due to familiarity,

> **Figure 5. Orchestration Agent (OA):** *(diagram image not reproduced here)* Manages instrument assignments for melody and harmony. Adjusts instruments, switches orchestration, and sets pitch ranges with information from the current loop and HA. Coordinates with HA's arpeggiator and manages instrument-family ranges. Submits final MIDI events.

which tends to be more prolonged in incidental than focused music settings. This could account for the 'repeating' music preference. A significant decrease in liking might require at least 32 repetitions, or roughly 80 minutes of continuous gameplay, to manifest. More information about the test can be found on [35].

PAMG has shown versatility in game music creation, yet it primarily produces western tonal orchestral scores. Adapting it for other styles as for example EDM music, a common genre employed in videogames, requires significant changes in algorithms and instrument management. For instance, EDM involves modifying bass ranges, simplifying rhythmic complexity, and generating continuous and idiomatic aural changes. In terms of real-time interaction, while PAMG allows for immediate parameter adjustments, this can disrupt musical phrasing, which is often tied to rhythmic structures like meter and tempo. Currently, some parameters are quantized to sync with phrases or measures, ensuring musical coherence, but the balance between real-time responsiveness

> **Figure 7. Seeded Phrase Generator.** *(diagram image not reproduced here)* It generates seeds for rhythm and pitch, changing music content per chord or phrase and provides improvisational passages with 0-seeded values.

> **Figure 6. Multi-Parameter Preset Interpolator.** *(diagram image not reproduced here)* It manages agent parameters and presets, and also interpolates among presets, which facilitates seamless musical transitions and allows saving and assigning multi-parameter presets to themes (XY pads' corners).

and phrase integrity is an ongoing challenge. The system's control of resolution for musical changes also poses issues. Given music's discrete nature, using full MIDI ranges for certain parameters can result in no perceptible change, or conversely, abrupt musical shifts. This is partly mitigated by phrasing quantization and gradual transitions, but managing multiple simultaneous parameter changes remains complex. Integrating PAMG into game development raises several questions, including how it aligns with existing authoring systems, handles various game and music genres, and leverages automation to create value. Two primary concerns are its integration with a composer's aesthetic and its method to handle samples and timbre. The former could involve analyzing and translating existing game music to inform PAMG's outputs, possibly using machine learning or Markov chains. The latter, related to licensing and idiomatic textures, might require new approaches in sample management or re-synthesis. PAMG's future could also see composers using it more as an instrument, crafting adaptive generative music with clear authorship in the framework of co-creativity [15].

PAMG's approach aims to augment the granularity, diversity, and dynamics of adaptive game music setups, offering new creative and experiential possibilities in game music composition.

---

## References

[1] Amir Zaib Abbasi, Ding Hooi Ting, and Helmut Hlavacs. 2017. Engagement in Games: Developing an Instrument to Measure Consumer Videogame Engagement and Its Validation. https://doi.org/10.1155/2017/7363925 ISSN: 1687-7047 Pages: e7363925 Publisher: Hindawi Volume: 2017.

[2] Charles Ames. 1987. Automated Composition in Retrospect: 1956-1986. *Leonardo* 20, 2 (1987), 169–185. https://doi.org/10.2307/1578334 Publisher: The MIT Press.

[3] Charles Ames. 1989. The Markov Process as a Compositional Model: A Survey and Tutorial. *len Leonardo* 22, 2 (1989), 175–187. OCLC: 30366918912817.

[4] Grégoire Carpentier, Eric Daubresse, Marc Garcia Vitoria, Kenji Sakai, and Fernando Villanueva Carratero. 2012. Automatic Orchestration in Practice. *Computer Music Journal* 36, 3 (2012), 24–42. https://www.jstor.org/stable/23254380 Publisher: The MIT Press.

[5] Thomas Street Christensen. 2002. *The Cambridge history of Western music theory.* Cambridge, U.K. ; New York : Cambridge University Press. http://archive.org/details/cambridgehistory00chri

[6] Karen Collins. 2009. An Introduction to Procedural Music in Video Games. *Contemporary Music Review* 28, 1 (2009), 5–15. https://doi.org/10.1080/07494460802663983

[7] N Collins. 2000. Caring for the Instrumentalist in Automatic Orchestration. *Proceedings for Acoustics and Music: Theory and Applications* (2000), 32–38.

[8] David Cope. 1991. *Computers and musical style.* A-R Editions, Madison, Wis. OCLC: 23356215.

[9] David Cope and David Cope. 1996. *Experiments in musical intelligence.* Number v. 12 in The Computer music and digital audio series. A-R Editions, Madison, Wis.

[10] Carl Dahlhaus. 2014. Studies on the Origin of Harmonic Tonality. In *Studies on the Origin of Harmonic Tonality.* Princeton University Press. https://doi.org/10.1515/9781400861316

[11] Elmsley, A, Velardo, V, and Grooves, R. 2017. Deep Adaptation: How Generative Music Affects Engagement and Immersion in Interactive Experiences. https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/30583/ID%3A%2097442919-02C3-424B-9C18-B08D362CCC22.pdf?sequence=1

[12] Laura Ermi and Frans Mäyrä. 2005. Fundamental Components of the Gameplay Experience: Analysing Immersion.

[13] Philippe Esling, Grégoire Carpentier, and Carlos Agon. 2010. Dynamic Musical Orchestration Using Genetic Algorithms and a Spectro-Temporal Description of Musical Instruments. In *Applications of Evolutionary Computation (Lecture Notes in Computer Science)*, Cecilia Di Chio, Anthony Brabazon, Gianni A. Di Caro, Marc Ebner, Muddassar Farooq, Andreas Fink, Jörn Grahl, Gary Greenfield, Penousal Machado, Michael O'Neill, Ernesto Tarantino, and Neil Urquhart (Eds.). Springer, Berlin, Heidelberg, 371–380. https://doi.org/10.1007/978-3-642-12242-2_38

[14] Paul Gilreath and Jim Aikin. 2004. *The Guide To MIDI Orchestration* (3rd edition ed.). Musicworks, Marietta, GA.

[15] Artemi-Maria Gioti. 2021. Artificial Intelligence for Music Composition. In *Handbook of Artificial Intelligence for Music: Foundations, Advanced Approaches, and Developments for Creativity*, Eduardo Reck Miranda (Ed.). Springer International Publishing, Cham, 53–73. https://doi.org/10.1007/978-3-030-72116-9_3

[16] Roni Y. Granot and Zohar Eitan. 2011. Musical Tension and the Interaction of Dynamic Auditory Parameters. *Music Perception* 28, 3 (Feb. 2011), 219–246. https://doi.org/10.1525/mp.2011.28.3.219 Publisher: University of California Press.

[17] Mark Grimshaw and Gareth Schott. 2008. A Conceptual Framework for the Analysis of First-Person Shooter Audio and its Potential Use for Game Engines. *International Journal of Computer Games Technology* 2008 (Jan. 2008), e720280. https://doi.org/10.1155/2008/720280 Publisher: Hindawi.

[18] Christopher Hasty. 2020. *Meter as Rhythm: 20th Anniversary Edition* (new to this edition:, new to this edition: ed.). Oxford University Press, Oxford, New York.

[19] Hermann von Helmholtz. 1885. *On the Sensations of Tone as a Physiological Basis for the Theory of Music.* Longmans, Green. Google-Books-ID: GwE6AAAAIAAJ.

[20] Ronald G. Heyduk. 1975. Rated preference for musical compositions as it relates to complexity and exposure frequency. *Perception & psychophysics* 17, 1 (1975), 84–90. https://doi.org/10.3758/BF03204003

[21] Lejaren Hiller and Leonard M. (Leonard Maxwell) Isaacson. 1959. *Experimental music; composition with an electronic computer.* New York, McGraw-Hill. http://archive.org/details/experimentalmusi00hill

[22] David Huron. 2006. *Sweet Anticipation: Music and the Psychology of Expectation.* The MIT Press. https://doi.org/10.7551/mitpress/6575.001.0001

[23] Patrick Edward Hutchings and Jon McCormack. 2020. Adaptive Music Composition for Games. *IEEE Transactions on Games* 12, 3 (Sept. 2020), 270–280. https://doi.org/10.1109/TG.2019.2921979

[24] Charlene Jennett, Anna L. Cox, Paul Cairns, Samira Dhoparee, Andrew Epps, Tim Tijs, and Alison Walton. 2008. Measuring and defining the experience of immersion in games. *International Journal of Human-Computer Studies* 66, 9 (Sept. 2008), 641–661. https://doi.org/10.1016/j.ijhcs.2008.04.004

[25] Kristoffer Jensen and David G. Hebert. 2016. Evaluation and Prediction of Harmonic Complexity Across 76 Years of Billboard 100 Hits. In *Music, Mind, and Embodiment (Lecture Notes in Computer Science)*, Richard Kronland-Martinet, Mitsuko Aramaki, and Sølvi Ystad (Eds.). Springer International Publishing, Cham, 283–296. https://doi.org/10.1007/978-3-319-46282-0_18

[26] Jiulin Zhang and Xiaoqing Fu. 2015. The Influence of Background Music of Video Games on Immersion. *Journal of Psychology & Psychotherapy* 5, 4 (2015), 191. https://doi.org/10.4172/2161-0487.1000191

[27] Michael Keith. 1991. *From Polychords to Pólya: Adventures in Musical Combinatorics.* Vinculum Press. Google-Books-ID: s5BJAAAACAAJ.

[28] Stefan M. Kostka. 2013. *Tonal harmony: with an introduction to twentieth-century music* (7th ed. ed.). McGraw-Hill, New York.

[29] Carol L. Krumhansl. 2001. *Cognitive Foundations of Musical Pitch.* Oxford University Press. https://doi.org/10.1093/acprof:oso/9780195148367.001.0001

[30] Mikael Laurson and Mika Kuuskankare. 2007. A Constraint Based Approach to Musical Textures and Instrumental Writing. https://www.semanticscholar.org/paper/A-Constraint-Based-Approach-to-Musical-Textures-and-Laurson-Kuuskankare/3ad6ee366d7e4d526dbf2b0bb76f1f778c8974b5

[31] Fred Lerdahl. 1988. Tonal Pitch Space. *Music Perception: An Interdisciplinary Journal* 5, 3 (1988), 315–349. https://doi.org/10.2307/40285402 Publisher: University of California Press.

[32] Fred Lerdahl and Ray Jackendoff. 1983. *A generative theory of tonal music.* MIT Press, Cambridge, Mass. OCLC: 8729599.

[33] Fred Lerdahl and Carol L. Krumhansl. 2007. Modeling Tonal Tension. *Music Perception: An Interdisciplinary Journal* 24, 4 (2007), 329–366. https://doi.org/10.1525/mp.2007.24.4.329 Publisher: University of California Press.

[34] Alvaro E. Lopez Duarte. 2020. Algorithmic interactive music generation in videogames. *SoundEffects - An Interdisciplinary Journal of Sound and Sound Experience* 9, 1 (Jan. 2020), 38–59. https://doi.org/10.7146/se.v9i1.118245

[35] Alvaro E. Lopez Duarte. 2023. *A Progressive-Adaptive Music Generator for Videogames (PAMG): an Approach to Real-Time Algorithmic Composition.* Ph. D. Dissertation. UC Riverside. https://escholarship.org/uc/item/1zh86812

[36] Michael George Luby. 1996. *Pseudorandomness and cryptographic applications.* Princeton University Press, Princeton, NJ.

[37] Guy Madison and Gunilla Schiölde. 2017. Repeated Listening Increases the Liking for Music Regardless of Its Complexity: Implications for the Appreciation and Aesthetics of Music. *Frontiers in Neuroscience* 11 (2017). https://www.frontiersin.org/articles/10.3389/fnins.2017.00147

[38] Edited by Alex McLean and Roger T. Dean (Eds.). 2018. *The Oxford Handbook of Algorithmic Music.* Oxford University Press, Oxford, New York.

[39] María Navarro-Cáceres, Marcelo Caetano, Gilberto Bernardes, Mercedes Sánchez-Barba, and Javier Merchán Sánchez-Jara. 2020. A Computational Model of Tonal Tension Profile of Chord Progressions in the Tonal Interval Space. *Entropy* 22, 11 (Nov. 2020), 1291. https://doi.org/10.3390/e22111291

[40] Gerhard Nierhaus. 2009. *Algorithmic composition: paradigms of automated music generation.* Springer, Wien ; New York. http://dx.doi.org/10.1007/978-3-211-75540-2

[41] J Norris. 1998. *Markov chains* (1st pbk. ed. ed.). Cambridge University Press, Cambridge UK ;;New York.

[42] George Papadopoulos and Geraint Wiggins. 1999. AI Methods for Algorithmic Composition: A Survey, a Critical View and Future Prospects. *Proceedings from the AISB'99 Symposium on Musical Creativity* (1999).

[43] Richard Parncutt. 1989. *Harmony: a psychoacoustical approach.* Number 19 in Springer series in information sciences. Springer-Verlag, Berlin ;.

[44] David Plans and Davide Morelli. 2012. Experience-Driven Procedural Music Generation for Games. *IEEE Transactions on Computational Intelligence and AI in Games* 4, 3 (Sept. 2012), 192–198. https://doi.org/10.1109/TCIAIG.2012.2212899

[45] Cale Plut and Philippe Pasquier. 2020. Generative music in video games: State of the art, challenges, and prospects. *Entertainment Computing* 33 (March 2020), 100337. https://doi.org/10.1016/j.entcom.2019.100337

[46] Cale Plut, Philippe Pasquier, Jeff Ens, and Renaud Bougueng Tchemeube. 2022. PreGLAM-MMM: Application and evaluation of affective adaptive generative music in video games. https://doi.org/10.1145/3555858.3555947 Pages: 11.

[47] Dirk-Jan Povel and Peter Essens. 1985. Perception of Temporal Patterns. *Music Perception: An Interdisciplinary Journal* 2, 4 (1985), 411–440. https://doi.org/10.2307/40285311 Publisher: University of California Press.

[48] David Psenicka. 2003. SPORCH: An Algorithm for Orchestration Based on Spectral Analyses of Recorded Sounds. (Jan. 2003).

[49] Robert Rowe. 1993. *Interactive music systems: machine listening and composing.* MIT Press, Cambridge, Mass.

[50] Germán Ruiz Marcos. 2022. Tension-driven Automatic Music Generation. (2022). https://doi.org/10.21954/OU.RO.000142CF Publisher: The Open University.

[51] E. Glenn Schellenberg, Isabelle Peretz, and Sandrine Vieillard. 2008. Liking for happy- and sad-sounding music: Effects of exposure. *Cognition and Emotion* 22, 2 (Feb. 2008), 218–237. https://doi.org/10.1080/02699930701350753 Publisher: Routledge _eprint: https://doi.org/10.1080/02699930701350753.

[52] Marco Scirea, Julian Togelius, Peter Eklund, and Sebastian Risi. 2017. Affective evolutionary music composition with MetaCompose. *Genetic Programming and Evolvable Machines* 18, 4 (Dec. 2017), 433–465. https://doi.org/10.1007/s10710-017-9307-y

[53] I. Shmulevich and D.-J. Povel. 1998. Rhythm complexity measures for music pattern recognition. In *1998 IEEE Second Workshop on Multimedia Signal Processing (Cat. No.98EX175)*. 167–172. https://doi.org/10.1109/MMSP.1998.738930

[54] Mark J. Steedman. 1984. A Generative Grammar for Jazz Chord Sequences. *Music Perception* 2, 1 (Oct. 1984), 52–77. https://doi.org/10.2307/40285282

[55] Michael Sweet. 2015. *Writing interactive music for video games a composer's guide.* Addison-Wesley, Upper Saddle River, NJ; Boston; Indianapolis; San Francisco; New York; Toronto; Montreal; London; Munich; Paris; Madrid; Capetown; Sydney; Tokyo; Singapore; Mexico City. OCLC: 946779709.

[56] Kıvanç Tatar and Philippe Pasquier. 2019. Musical agents: A typology and state of the art towards Musical Metacreation. *Journal of New Music Research* 48, 1 (Jan. 2019), 56–105. https://doi.org/10.1080/09298215.2018.1511736 Publisher: Routledge _eprint: https://doi.org/10.1080/09298215.2018.1511736.

[57] David Temperley. 2004. *The Cognition of Basic Musical Structures.* MIT Press. Google-Books-ID: IDoLEvTQuewC.

[58] Joseph M. Thomassen. 1982. Melodic accent: Experiments and a tentative model. *The Journal of the Acoustical Society of America* 71, 6 (June 1982), 1596–1605. https://doi.org/10.1121/1.387814 Publisher: Acoustical Society of America.

[59] Julian Togelius, Georgios N. Yannakakis, Kenneth O. Stanley, and Cameron Browne. 2011. Search-Based Procedural Content Generation: A Taxonomy and Survey. *IEEE Transactions on Computational Intelligence and AI in Games* 3, 3 (Sept. 2011), 172–186. https://doi.org/10.1109/TCIAIG.2011.2148116 Conference Name: IEEE Transactions on Computational Intelligence and AI in Games.

[60] G. Toussaint. 2012. The Pairwise Variability Index as a Tool in Musical Rhythm Analysis. https://www.semanticscholar.org/paper/The-Pairwise-Variability-Index-as-a-Tool-in-Musical-Toussaint/abecf85144a253305a01c77d85f19bbddd22accd

[61] Godfried T. Toussaint and Konstantinos Trochidis. 2018. On Measuring the Complexity of Musical Rhythm. In *2018 9th IEEE Annual Ubiquitous Computing, Electronics & Mobile Communication Conference (UEMCON)*. 753–757. https://doi.org/10.1109/UEMCON.2018.8796634

[62] Dmitri Tymoczko. 2023. *Tonality: An Owner's Manual.* Oxford University Press, Incorporated, Oxford, UNITED STATES. http://ebookcentral.proquest.com/lib/ucr/detail.action?docID=7294520

[63] Paul C. Vitz. 1964. Preferences for rates of information presented by sequences of tones. *Journal of experimental psychology* 68, 2 (1964), 176–183. https://doi.org/10.1037/h0043402 Place: United States Publisher: American Psychological Association.

[64] Peter Vorderer and Jennings Bryant (Eds.). 2006. *Playing Video Games: Motives, Responses, and Consequences* (1st edition ed.). Routledge, Mahwah, N.J.

[65] Lei Wang, Ziyi Zhao, Hanwei Liu, Junwei Pang, Yi Qin, and Qidi Wu. 2023. A Review of Intelligent Music Generation Systems. https://doi.org/10.48550/arXiv.2211.09124 arXiv:2211.09124 [cs, eess].

[66] Alexander Wharton and Karen Collins. 2011. Subjective Measures of the Influence of Music Customization on the Video Game Play Experience: A Pilot Study. *Game Studies* 11, 2 (May 2011). https://gamestudies.org/1102/articles/wharton_collins

[67] T. Winkler. 2001. *Composing Interactive Music: Techniques and Ideas Using Max.* The MIT Press. https://www.biblio.com/book/composing-interactive-music-techniques-ideas-using/d/1567101032

[68] Richard T.A. Wood, Mark D. Griffiths, and Adrian Parke. 2007. Experiences of Time Loss among Videogame Players: An Empirical Study. *CyberPsychology & Behavior* 10, 1 (Feb. 2007), 38–44. https://doi.org/10.1089/cpb.2006.9994

[69] René Wooller and Andrew R. Brown. 2005. Investigating morphing algorithms for generative music. In *Third Iteration: Third International Conference on Generative Systems in the Electronic Arts, Melbourne, Australia.*

---

*Received 2024-06-02; accepted 2024-07-02*
