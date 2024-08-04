/*
 * Copyright (C) 2021, 2023-2024 Jonathan Feenstra
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
use esplugin::GameId;
use esplugin::ParseOptions;
use esplugin::Plugin;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::io::Cursor;

#[pyclass(name = "Plugin")]
struct PyPlugin {
    plugin: Plugin,
}

#[pymethods]
impl PyPlugin {
    #[new]
    fn new(game: &str, path: &str) -> PyResult<Self> {
        let game_id = {
            match game {
                "Fallout4" => GameId::Fallout4,
                "SkyrimSE" => GameId::SkyrimSE,
                "Starfield" => GameId::Starfield,
                _ => return Err(PyErr::new::<PyValueError, _>("Invalid game")),
            }
        };
        let plugin = Plugin::new(game_id, std::path::Path::new(path));
        Ok(Self { plugin })
    }

    fn parse(&mut self, input: &[u8], load_header_only: bool) -> PyResult<()> {
        let cursor = Cursor::new(input);

        match self.plugin.parse_reader(
            cursor,
            match load_header_only {
                true => ParseOptions::header_only(),
                false => ParseOptions::whole_plugin(),
            },
        ) {
            Ok(()) => Ok(()),
            Err(e) => Err(PyErr::new::<PyValueError, _>(e.to_string())),
        }
    }

    fn parse_file(&mut self, load_header_only: bool) -> PyResult<()> {
        match self.plugin.parse_file(match load_header_only {
            true => ParseOptions::header_only(),
            false => ParseOptions::whole_plugin(),
        }) {
            Ok(()) => Ok(()),
            Err(e) => Err(PyErr::new::<PyValueError, _>(e.to_string())),
        }
    }

    fn is_light_plugin(&self) -> bool {
        self.plugin.is_light_plugin()
    }

    fn is_valid_as_light_plugin(&self) -> PyResult<bool> {
        match self.plugin.is_valid_as_light_plugin() {
            Ok(b) => Ok(b),
            Err(e) => Err(PyErr::new::<PyValueError, _>(e.to_string())),
        }
    }

    fn is_medium_plugin(&self) -> bool {
        self.plugin.is_medium_plugin()
    }

    fn is_valid_as_medium_plugin(&self) -> PyResult<bool> {
        match self.plugin.is_valid_as_medium_plugin() {
            Ok(b) => Ok(b),
            Err(e) => Err(PyErr::new::<PyValueError, _>(e.to_string())),
        }
    }

    fn is_update_plugin(&self) -> bool {
        self.plugin.is_update_plugin()
    }

    fn is_valid_as_update_plugin(&self) -> PyResult<bool> {
        match self.plugin.is_valid_as_update_plugin() {
            Ok(b) => Ok(b),
            Err(e) => Err(PyErr::new::<PyValueError, _>(e.to_string())),
        }
    }
}

#[pymodule]
#[pyo3(name = "esplugin")]
fn py_esplugin(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyPlugin>()?;
    Ok(())
}
