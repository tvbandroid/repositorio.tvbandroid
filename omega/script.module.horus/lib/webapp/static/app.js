/* EKHorus - The channel browser in the browser.
 *
 * The whole catalogue arrives in one request and is filtered here, so searching and
 * changing facet are instant and cost the engine nothing. Roughly 1800 channels weigh a
 * couple of hundred KB over the local network, which is the price of never waiting again.
 */

'use strict';

var PASO = 60;              // cards drawn per batch while scrolling
var SONDEO_MS = 5000;       // how often the television is asked what it is playing

var estado = {
  canales: [],
  etiquetas: {},
  sinDato: '_sin',
  faceta: 'categorias',
  clave: '',
  texto: '',
  filtrados: [],
  pintados: 0,
  canal: null,
  externo: false
};

var $ = function (id) { return document.getElementById(id); };

/* ── Helpers ─────────────────────────────────────────────────────────── */

function sinTildes(t) {
  return (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function etiqueta(campo, clave) {
  if (clave === estado.sinDato) { return 'Sin especificar'; }
  var tabla = estado.etiquetas[campo] || {};
  return tabla[clave] || clave.replace(/_/g, ' ').toUpperCase();
}

function iconoFaceta(campo, clave) {
  if (campo === 'categorias') { return '/media/categorias/' + clave + '.png'; }
  if (campo === 'paises' && clave !== estado.sinDato) { return '/media/banderas/' + clave + '.png'; }
  return '';
}

// A stable colour per channel, so the ones with no logo are still told apart at a glance.
function tono(nombre) {
  var suma = 0;
  for (var i = 0; i < nombre.length; i++) { suma = (suma * 31 + nombre.charCodeAt(i)) % 360; }
  return suma;
}

function iniciales(nombre) {
  var palabras = nombre.replace(/[^\w\sÀ-ÿ]/g, ' ').split(/\s+/).filter(Boolean);
  if (!palabras.length) { return '?'; }
  return (palabras[0][0] + (palabras[1] ? palabras[1][0] : '')).toUpperCase();
}

function pintarLogo(destino, canal) {
  destino.innerHTML = '';
  destino.style.background = '';

  if (canal.logo) {
    var img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = '';
    img.src = canal.logo;
    img.onerror = function () { destino.innerHTML = ''; ponerIniciales(destino, canal); };
    destino.appendChild(img);
    return;
  }

  ponerIniciales(destino, canal);
}

function ponerIniciales(destino, canal) {
  destino.style.background = 'linear-gradient(140deg, hsl(' + tono(canal.nombre) +
    ',34%,26%), hsl(' + ((tono(canal.nombre) + 40) % 360) + ',30%,17%))';
  destino.textContent = iniciales(canal.nombre);
}

function decir(texto) {
  var caja = $('aviso_flotante');
  caja.textContent = texto;
  caja.hidden = false;
  clearTimeout(decir._t);
  decir._t = setTimeout(function () { caja.hidden = true; }, 2600);
}

// Plain http is not a secure context, so navigator.clipboard does not exist here. On a
// phone the only thing left is the old selection trick.
function copiar(texto) {
  var area = document.createElement('textarea');
  area.value = texto;
  area.setAttribute('readonly', '');
  area.style.cssText = 'position:fixed;top:-1000px';
  document.body.appendChild(area);
  area.select();
  area.setSelectionRange(0, texto.length);

  var bien = false;
  try { bien = document.execCommand('copy'); } catch (e) { bien = false; }
  document.body.removeChild(area);

  decir(bien ? 'Copiado' : 'No se pudo copiar; mantén pulsado el texto');
  return bien;
}

function pedir(ruta, opciones) {
  return fetch(ruta, opciones).then(function (r) {
    if (!r.ok) { throw new Error('HTTP ' + r.status); }
    return r.json();
  });
}

/* ── Facets and chips ────────────────────────────────────────────────── */

function contar(campo) {
  var cuentas = {};

  estado.canales.forEach(function (canal) {
    var valores = canal[campo] && canal[campo].length ? canal[campo] : [estado.sinDato];
    valores.forEach(function (v) { cuentas[v] = (cuentas[v] || 0) + 1; });
  });

  return Object.keys(cuentas)
    .map(function (c) { return { clave: c, nombre: etiqueta(campo, c), total: cuentas[c] }; })
    .sort(function (a, b) {
      if ((a.clave === estado.sinDato) !== (b.clave === estado.sinDato)) {
        return a.clave === estado.sinDato ? 1 : -1;
      }
      return b.total - a.total;
    });
}

function pintarFacetas() {
  var campos = [['categorias', 'Categorías'], ['paises', 'Países'], ['idiomas', 'Idiomas']];
  var caja = $('facetas');
  caja.innerHTML = '';

  campos.forEach(function (par) {
    var b = document.createElement('button');
    b.textContent = par[1];
    if (par[0] === estado.faceta) { b.className = 'activa'; }
    b.onclick = function () {
      estado.faceta = par[0];
      estado.clave = '';
      pintarFacetas();
      pintarChips();
      filtrar();
    };
    caja.appendChild(b);
  });
}

function pintarChips() {
  var caja = $('chips');
  caja.innerHTML = '';

  var filas = [{ clave: '', nombre: 'Todos', total: estado.canales.length }]
    .concat(contar(estado.faceta));

  filas.forEach(function (fila) {
    var chip = document.createElement('button');
    chip.className = 'chip' + (fila.clave === estado.clave ? ' activa' : '');

    var icono = fila.clave ? iconoFaceta(estado.faceta, fila.clave) : '';
    if (icono) {
      var img = document.createElement('img');
      img.src = icono;
      img.alt = '';
      img.onerror = function () { img.remove(); };
      chip.appendChild(img);
    }

    chip.appendChild(document.createTextNode(fila.nombre));

    var cuenta = document.createElement('span');
    cuenta.className = 'cuenta';
    cuenta.textContent = fila.total;
    chip.appendChild(cuenta);

    chip.onclick = function () {
      estado.clave = fila.clave;
      pintarChips();
      filtrar();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    caja.appendChild(chip);
  });
}

/* ── Filtering and the grid ──────────────────────────────────────────── */

function filtrar() {
  var texto = sinTildes(estado.texto.trim());
  var campo = estado.faceta;
  var clave = estado.clave;

  estado.filtrados = estado.canales.filter(function (canal) {
    if (clave) {
      var valores = canal[campo] && canal[campo].length ? canal[campo] : [estado.sinDato];
      if (valores.indexOf(clave) < 0) { return false; }
    }
    return !texto || sinTildes(canal.nombre).indexOf(texto) >= 0;
  });

  $('rejilla').innerHTML = '';
  estado.pintados = 0;
  rellenar();

  var vacio = $('vacio');
  vacio.hidden = estado.filtrados.length > 0;
  vacio.textContent = texto ? 'Ningún canal se llama así.' : 'Aquí no hay canales.';
}

function tarjeta(canal) {
  var boton = document.createElement('button');
  boton.className = 'tarjeta';

  var logo = document.createElement('div');
  logo.className = 'logo';
  pintarLogo(logo, canal);
  boton.appendChild(logo);

  var nombre = document.createElement('div');
  nombre.className = 'nombre';
  nombre.textContent = canal.nombre;
  boton.appendChild(nombre);

  var pie = document.createElement('div');
  pie.className = 'pie';

  var pais = (canal.paises || [])[0];
  if (pais && pais !== estado.sinDato) {
    var bandera = document.createElement('img');
    bandera.src = '/media/banderas/' + pais + '.png';
    bandera.alt = '';
    bandera.loading = 'lazy';
    bandera.onerror = function () { bandera.remove(); };
    pie.appendChild(bandera);
  }

  var cat = (canal.categorias || [])[0];
  if (cat) {
    var texto = document.createElement('span');
    texto.textContent = etiqueta('categorias', cat);
    pie.appendChild(texto);
  }

  if (canal.estado !== 2) {
    var marca = document.createElement('span');
    marca.className = 'dudoso';
    marca.textContent = 'dudoso';
    pie.appendChild(marca);
  }

  boton.appendChild(pie);
  boton.onclick = function () { abrirFicha(canal); };

  return boton;
}

function pintarMas() {
  var rejilla = $('rejilla');
  var hasta = Math.min(estado.pintados + PASO, estado.filtrados.length);
  var trozo = document.createDocumentFragment();

  for (var i = estado.pintados; i < hasta; i++) { trozo.appendChild(tarjeta(estado.filtrados[i])); }

  rejilla.appendChild(trozo);
  estado.pintados = hasta;
}

function centinelaALaVista() {
  return $('centinela').getBoundingClientRect().top < window.innerHeight + 400;
}

function rellenar() {
  // One batch is not always enough. The observer only fires when the sentinel CHANGES
  // whether it is in view, so a filter with seventy results, or a wide screen, would draw
  // the first sixty and stop there for ever with the rest unreachable.
  do {
    pintarMas();
  } while (estado.pintados < estado.filtrados.length && centinelaALaVista());
}

/* ── Layers, and the phone's back gesture ────────────────────────────── */

/* Back has to close what is on top instead of leaving the page, which is what a phone user
 * expects from the gesture. Each layer gets its own history entry carrying how deep it is,
 * and closing ALWAYS goes through the browser: nothing is hidden by hand.
 *
 * The depth is what makes it sound. Reading it back means any number of steps at once
 * lands right, and it avoids pushing a new entry from inside the popstate handler, which
 * measured on the phone did not register in time and let the next Back leave the page. */

var pila = [];

function abrirCapa(id) {
  $(id).hidden = false;
  pila.push(id);
  history.pushState({ ekh: pila.length }, '');
}

function ocultarCapa(id) {
  $(id).hidden = true;
  if (id === 'reproductor') { pararVideo(); }
}

function cerrarCapa(cuantas) {
  if (pila.length) {
    history.go(-Math.min(cuantas || 1, pila.length));
  }
}

window.addEventListener('popstate', function () {
  var nivel = (history.state && history.state.ekh) || 0;

  while (pila.length > nivel) { ocultarCapa(pila.pop()); }
});

/* ── One channel ─────────────────────────────────────────────────────── */

function abrirFicha(canal) {
  estado.canal = canal;

  $('ficha_nombre').textContent = canal.nombre;
  pintarLogo($('ficha_logo'), canal);

  var partes = [];
  (canal.categorias || []).slice(0, 2).forEach(function (c) { partes.push(etiqueta('categorias', c)); });
  (canal.paises || []).slice(0, 2).forEach(function (p) { partes.push(etiqueta('paises', p)); });
  if (canal.estado !== 2) { partes.push('enlace dudoso'); }
  $('ficha_pista').textContent = partes.join(' · ');

  abrirCapa('ficha');
}

function conEnlaces(canal) {
  return pedir('/api/enlaces?infohash=' + encodeURIComponent(canal.infohash));
}

/* ── Playing here ────────────────────────────────────────────────────── */

function cargarHls() {
  if (window.Hls) { return Promise.resolve(); }

  return new Promise(function (bien, mal) {
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js';
    s.onload = bien;
    s.onerror = mal;
    document.head.appendChild(s);
  });
}

function verAqui(canal) {
  // The sheet is left underneath on purpose: the player covers it whole, and closing the
  // player brings back the channel you came from instead of dropping you in the grid.
  $('repro_nombre').textContent = canal.nombre;
  abrirCapa('reproductor');

  // The engine can take half a minute to open a channel, and a black rectangle with
  // nothing on it is indistinguishable from a button that did not work.
  esperandoVideo();

  var video = $('video');
  video.onplaying = function () { $('repro_aviso').hidden = true; };

  conEnlaces(canal).then(function (urls) {
    video.onerror = function () { avisarSinVideo(canal, urls); };

    // Safari and Android's browsers play an m3u8 straight from src, with no library and
    // no CORS getting in the way. That is the case this whole feature was built for.
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = urls.hls;
      video.play().catch(function () { /* the controls are there for them to press */ });
      return;
    }

    // A desktop browser needs a library. It is only fetched when it is needed, and it
    // does work: the engine answers with Access-Control-Allow-Origin, measured.
    cargarHls().then(function () {
      var hls = new window.Hls({ manifestLoadingTimeOut: 30000 });
      pararVideo.hls = hls;
      hls.loadSource(urls.hls);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play().catch(function () {}); });
      hls.on(window.Hls.Events.ERROR, function (_evento, dato) {
        if (dato && dato.fatal) { avisarSinVideo(canal, urls); }
      });
    }).catch(function () {
      avisarSinVideo(canal, urls, null, 'Este navegador no sabe reproducir la emisión '
                                        + 'por su cuenta.');
    });
  }).catch(function (e) {
    avisarSinVideo(canal, null, e);
  });
}

function esperandoVideo() {
  var caja = $('repro_aviso');
  caja.innerHTML = '<div class="cargando"><span class="rueda"></span>'
                 + 'Abriendo el canal. Tarda unos segundos.</div>';
  caja.hidden = false;
}

function avisarSinVideo(canal, urls, error, motivo) {
  var caja = $('repro_aviso');
  caja.innerHTML = '';

  var p = document.createElement('p');
  p.textContent = motivo || (error
    ? 'No se pudo preguntar por el canal: ' + error.message
    : 'No se pudo abrir el canal. Hace falta AceStream o AceServe arrancado.');
  caja.appendChild(p);

  if (urls) {
    var b = document.createElement('button');
    b.className = 'accion';
    b.textContent = 'Copiar el enlace para VLC';
    b.onclick = function () { copiar(urls.directo); };
    caja.appendChild(b);
  }

  var t = document.createElement('button');
  t.className = 'accion principal';
  t.textContent = 'Verlo en la tele';
  t.onclick = function () {
    verEnTele(canal);
    // Two layers to shut: the player and the channel sheet underneath it.
    cerrarCapa(2);
  };
  caja.appendChild(t);

  caja.hidden = false;
}

function pararVideo() {
  var video = $('video');
  video.pause();
  // Without this, the src being cleared below fires the error handler of the channel we
  // have just left and the notice would pop up over the grid.
  video.onerror = null;
  video.onplaying = null;

  if (pararVideo.hls) {
    pararVideo.hls.destroy();
    pararVideo.hls = null;
  }

  video.removeAttribute('src');
  video.load();
}

/* ── Playing on the television ───────────────────────────────────────── */

/* The engine takes its time opening a channel; measured against a real one, up to half a
 * minute. Until then the television reports nothing playing, and with no sign of life the
 * only reasonable thing left to think is that the button did not work. So the bar says so
 * from the first moment, and the status takes it over as soon as there is a picture.
 *
 * On Android the channel goes out to the engine's own application, so that picture never
 * arrives inside Kodi. There the bar says what really happened and steps aside. */

var ABRIENDO_MS = 60000;
var FUERA_MS = 8000;
var abriendo = 0;

function verEnTele(canal) {
  var fuera = estado.externo;

  abriendo = Date.now() + (fuera ? FUERA_MS : ABRIENDO_MS);
  pintarBarraTele(true, (fuera ? 'Mandado a la tele: ' : 'Abriendo en la tele: ')
                        + canal.nombre, !fuera);

  pedir('/api/tele', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ infohash: canal.infohash, nombre: canal.nombre, logo: canal.logo })
  }).catch(function (e) {
    abriendo = 0;
    pintarBarraTele(false);
    decir('No se pudo mandar a la tele: ' + e.message);
  });
}

function pararTele() {
  abriendo = 0;
  pintarBarraTele(false);

  pedir('/api/parar', { method: 'POST' })
    .then(function () { setTimeout(mirarEstado, 800); })
    .catch(function (e) { decir('No se pudo parar: ' + e.message); });
}

function pintarBarraTele(visible, texto, conParar) {
  $('tele_barra').hidden = !visible;
  // With playback outside Kodi there is nothing here to stop, and a button that does
  // nothing is worse than no button.
  $('btn_tele_parar').hidden = conParar === false;
  if (texto) { $('tele_txt').textContent = texto; }
}

/* ── Status ──────────────────────────────────────────────────────────── */

function mirarEstado() {
  // With the engine switched off the answer takes four seconds, which is close to the
  // polling interval; without this the requests would pile up on top of each other.
  if (mirarEstado.enVuelo) { return Promise.resolve(); }
  mirarEstado.enVuelo = true;

  return pedir('/api/estado').then(function (datos) {
    var motor = datos.motor || {};
    var total = (datos.catalogo || {}).total || 0;

    // While it works, the header talks about channels and nothing else. What is behind
    // them is only worth naming when there is a problem to solve.
    $('punto').className = 'punto ' + (motor.vivo ? 'vivo' : 'muerto');
    $('estado_txt').textContent = motor.vivo
      ? total + ' canales'
      : 'Sin conexión';

    $('mas_total').textContent = total;
    $('fila_fallo').hidden = motor.vivo;
    $('mas_fallo').textContent = motor.vivo
      ? ''
      : 'nada responde en ' + motor.direccion;

    var tele = datos.kodi || {};
    estado.externo = !!tele.externo;

    if (tele.reproduciendo) {
      abriendo = 0;
      pintarBarraTele(true, tele.titulo || 'Reproduciendo en la tele', true);
    } else if (Date.now() >= abriendo) {
      pintarBarraTele(false);
    }

    return datos;
  }).catch(function () {
    $('punto').className = 'punto muerto';
    $('estado_txt').textContent = 'Sin conexión con Kodi';
  }).then(function () {
    mirarEstado.enVuelo = false;
  });
}

/* ── Catalogue ───────────────────────────────────────────────────────── */

function cargando(mensaje) {
  $('rejilla').innerHTML = '<div class="cargando"><span class="rueda"></span>' +
    mensaje + '</div>';
}

function cargarCatalogo(forzar) {
  cargando(forzar ? 'Actualizando la lista de canales…'
                  : 'Cargando la lista de canales…');
  $('aviso').hidden = true;
  $('vacio').hidden = true;

  return pedir('/api/catalogo' + (forzar ? '?forzar=1' : '')).then(function (datos) {
    estado.canales = datos.canales || [];
    estado.etiquetas = datos.etiquetas || {};
    estado.sinDato = datos.sin_dato || '_sin';

    $('enlace_m3u').textContent = location.origin + '/api/lista.m3u';

    if (!estado.canales.length) {
      $('rejilla').innerHTML = '';
      sinCatalogo();
      return;
    }

    pintarFacetas();
    pintarChips();
    filtrar();
  }).catch(function (e) {
    $('rejilla').innerHTML = '';
    sinCatalogo(e);
  });
}

function sinCatalogo(error) {
  var aviso = $('aviso');
  aviso.innerHTML = '';

  var titulo = document.createElement('b');
  titulo.textContent = 'No hay lista de canales.';
  aviso.appendChild(titulo);

  var p = document.createElement('p');
  p.style.margin = '8px 0 14px';
  p.textContent = error
    ? 'Kodi no contestó: ' + error.message
    : 'No se ha podido cargar la lista. Hace falta AceStream o AceServe ' +
      'arrancado en este aparato.';
  aviso.appendChild(p);

  var b = document.createElement('button');
  b.className = 'accion';
  b.textContent = 'Volver a intentarlo';
  b.onclick = function () { cargarCatalogo(true); };
  aviso.appendChild(b);

  aviso.hidden = false;
}

/* ── Wiring ──────────────────────────────────────────────────────────── */

function arrancar() {
  var buscar = $('buscar');
  var espera = null;

  buscar.addEventListener('input', function () {
    $('btn_limpiar').hidden = !buscar.value;
    clearTimeout(espera);
    espera = setTimeout(function () {
      estado.texto = buscar.value;
      filtrar();
    }, 120);
  });

  $('btn_limpiar').onclick = function () {
    buscar.value = '';
    $('btn_limpiar').hidden = true;
    estado.texto = '';
    filtrar();
  };

  $('btn_aqui').onclick = function () { verAqui(estado.canal); };
  $('btn_tele').onclick = function () { verEnTele(estado.canal); cerrarCapa(); };
  $('btn_vlc').onclick = function () {
    conEnlaces(estado.canal).then(function (urls) { copiar(urls.directo); });
  };

  $('btn_cerrar_ficha').onclick = cerrarCapa;
  $('ficha').onclick = function (e) { if (e.target === $('ficha')) { cerrarCapa(); } };

  $('btn_cerrar_video').onclick = cerrarCapa;
  $('btn_tele_parar').onclick = pararTele;

  $('btn_mas').onclick = function () { abrirCapa('mas'); };
  $('btn_cerrar_mas').onclick = cerrarCapa;
  $('mas').onclick = function (e) { if (e.target === $('mas')) { cerrarCapa(); } };
  $('btn_copiar_m3u').onclick = function () { copiar($('enlace_m3u').textContent); };

  $('btn_actualizar').onclick = function () {
    cerrarCapa();
    cargarCatalogo(true);
  };

  new IntersectionObserver(function (entradas) {
    if (entradas[0].isIntersecting && estado.pintados < estado.filtrados.length) {
      rellenar();
    }
  }, { rootMargin: '400px' }).observe($('centinela'));

  // A phone with the screen off, or the page in a tab nobody is looking at, has no reason
  // to keep asking the television what it is playing.
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { mirarEstado(); }
  });

  mirarEstado();
  setInterval(function () {
    if (!document.hidden) { mirarEstado(); }
  }, SONDEO_MS);

  cargarCatalogo(false);
}

arrancar();
