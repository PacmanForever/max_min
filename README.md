# Max Min

[![Unit Tests](https://github.com/username/max-min/actions/workflows/tests_unit.yml/badge.svg)](https://github.com/username/max-min/actions/workflows/tests_unit.yml)
[![Component Tests](https://github.com/username/max-min/actions/workflows/tests_component.yml/badge.svg)](https://github.com/username/max-min/actions/workflows/tests_component.yml)
[![Validate HACS](https://github.com/username/max-min/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/username/max-min/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/username/max-min/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/username/max-min/actions/workflows/validate_hassfest.yml)

Una integració custom de Home Assistant que crea sensors de màxim i mínim basats en un sensor numèric seleccionat, amb suport per diferents períodes de temps.

## Característiques

- **Sensors de màxim/mínim**: Crea sensors que mantenen el valor màxim o mínim d'un sensor origen durant un període determinat
- **Períodes configurables**: Diari, setmanal, mensual o anual
- **Flexibilitat**: Crea sensors individuals (només màxim o només mínim) o en parella
- **Reset automàtic**: Al final de cada període, els sensors es resetejen al valor actual del sensor origen
- **Actualització en temps real**: Els sensors s'actualitzen immediatament quan canvia el valor del sensor origen

## Instal·lació

### HACS (recomanat)

1. Obre HACS a la teva instància de Home Assistant.
2. Ves a "Integracions" > "Repositoris personalitzats".
3. Afegeix `https://github.com/username/max-min` com a repositori personalitzat amb categoria "Integration".
4. Cerca "Max Min" i instal·la'l.
5. Reinicia Home Assistant.
6. Afegeix la integració a través de la UI.

### Manual

1. Descarrega la carpeta `max_min` de l'última release.
2. Copia-la a `custom_components/max_min` al directori de configuració de Home Assistant.
3. Reinicia Home Assistant.
4. Afegeix la integració a través de la UI.

## Configuració

Després de la instal·lació, afegeix la integració via la UI de Home Assistant:

1. Ves a Configuració > Dispositius i serveis > Afegeix integració.
2. Cerca "Max Min".
3. Selecciona el sensor origen (un sensor numèric existent).
4. Tria el període: Diari, Setmanal, Mensual o Anual.
5. Selecciona els tipus de sensors: Màxim, Mínim, o ambdós.

### Exemples de sensors creats

- **Max Temperature Diari**: Mostra el valor màxim de temperatura des de les 00:00 fins les 23:59 del dia actual
- **Min Humidity Setmanal**: Mostra el valor mínim d'humitat des del dilluns 00:00 fins el diumenge 23:59
- **Max Pressure Mensual**: Mostra el valor màxim de pressió des del dia 1 00:00 fins l'últim dia del mes 23:59
- **Min Voltage Anual**: Mostra el valor mínim de voltatge des de l'1 de gener 00:00 fins el 31 de desembre 23:59

## Com funciona

1. **Selecció del sensor**: L'usuari tria un sensor numèric existent a Home Assistant.
2. **Configuració del període**: Es defineix el cicle de temps (diari, setmanal, etc.).
3. **Creació dels sensors**: Es creen sensors de màxim i/o mínim amb noms descriptius.
4. **Acumulació de valors**: Durant el període, els sensors mantenen el màxim/mínim observat.
5. **Reset automàtic**: Al final del període, els sensors es resetejen al valor actual del sensor origen i comença un nou cicle.

### Períodes detallats

- **Diari**: De les 00:00 a les 23:59 del mateix dia. Reset a les 00:00 del dia següent.
- **Setmanal**: De dilluns 00:00 a diumenge 23:59. Reset a dilluns 00:00 de la setmana següent.
- **Mensual**: Del dia 1 00:00 a l'últim dia del mes 23:59. Reset al dia 1 00:00 del mes següent.
- **Anual**: De l'1 de gener 00:00 al 31 de desembre 23:59. Reset a l'1 de gener 00:00 de l'any següent.

## Automatitzacions

Pots utilitzar aquests sensors en automatitzacions, per exemple:

- Notificacions quan el màxim diari supera un llindar
- Registres històrics dels mínims setmanals
- Alertes per valors extrems mensuals

## Comportament amb reinicis de Home Assistant

Quan Home Assistant es reinicia, l'integració Max Min es comporta de la següent manera:

- **Valors acumulats es perden**: Els valors màxim i mínim acumulats durant el període actual es perden completament
- **Valor actual es preserva**: Només es manté el valor actual del sensor origen en el moment del reinici
- **Reset es reprograma**: El temporitzador de reset es recalcula basant-se en l'hora actual
- **Sensors no disponibles**: Si el sensor origen no està disponible durant el reinici, els sensors mostraran "No disponible"

**Nota important**: Aquesta integració no guarda els valors històrics en disc, per disseny. Si necessites persistència de dades, considera utilitzar la funcionalitat d'historial nativa de Home Assistant o bases de dades externes.

## Resolució de problemes

### El sensor no s'actualitza
- Verifica que el sensor origen existeix i té valors numèrics vàlids
- Comprova els logs de Home Assistant per errors

### El sensor mostra "No disponible"
- El sensor origen no està disponible o no té un valor numèric vàlid
- Espera que el sensor origen es torni a connectar

### Errors de configuració
- Assegura't que has seleccionat un sensor numèric existent
- Verifica que el període està correctament configurat

## Contribucions

Les contribucions són benvingudes! Si us plau, consulta [CONTRIBUTING.md](CONTRIBUTING.md) per detalls.

## Llicència

Aquest projecte està llicenciat sota la Llicència GPL-3.0 - consulta el fitxer [LICENSE](LICENSE) per detalls.