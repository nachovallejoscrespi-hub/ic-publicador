"""Bot de IC Consultores: publica en Instagram la próxima publicación pendiente de cola.json.

Variables (en GitHub: Settings > Secrets and variables > Actions):
  IG_TOKEN   (secret)    token de acceso de la app IC PUBLICADOR
  IG_USER_ID (variable)  ID de la cuenta de Instagram (17841414270725158)
  BASE_URL   (variable)  dirección pública de las imágenes, ej. https://usuario.github.io/ic-publicador/img/
  PRUEBA=1   (opcional)  arma todo pero no publica
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

API = 'https://graph.instagram.com/v23.0'
TOKEN = os.environ['IG_TOKEN']
USER = os.environ['IG_USER_ID']
BASE = os.environ['BASE_URL'].rstrip('/') + '/'
PRUEBA = os.environ.get('PRUEBA') == '1'


def llamar(metodo, ruta, **params):
    params['access_token'] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f'{API}/{ruta}'
    if metodo == 'GET':
        req = urllib.request.Request(url + '?' + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Error de Instagram ({e.code}) en {ruta}: {e.read().decode()}')


def esperar(contenedor):
    for _ in range(30):
        st = llamar('GET', contenedor, fields='status_code').get('status_code')
        if st == 'FINISHED':
            return
        if st in ('ERROR', 'EXPIRED'):
            raise SystemExit(f'El contenedor {contenedor} quedó en {st}')
        time.sleep(5)
    raise SystemExit(f'El contenedor {contenedor} no terminó de procesarse')


def publicar(p):
    urls = [BASE + i for i in p['imagenes']]
    for u in urls:  # control: que cada imagen esté online antes de pedirle nada a Instagram
        urllib.request.urlopen(urllib.request.Request(u, method='HEAD'), timeout=30)
    if PRUEBA:
        print('PRUEBA: estaría publicando', p['id'], p['titulo'], urls)
        return None
    if len(urls) == 1:
        c = llamar('POST', f'{USER}/media', image_url=urls[0], caption=p['texto'])['id']
    else:
        hijos = []
        for u in urls:
            h = llamar('POST', f'{USER}/media', image_url=u, is_carousel_item='true')['id']
            esperar(h)
            hijos.append(h)
        c = llamar('POST', f'{USER}/media', media_type='CAROUSEL', children=','.join(hijos), caption=p['texto'])['id']
    esperar(c)
    return llamar('POST', f'{USER}/media_publish', creation_id=c)['id']


def main():
    cola = json.load(open('cola.json', encoding='utf8'))
    hecho = json.load(open('publicado.json', encoding='utf8'))
    listos = {h['id'] for h in hecho}
    pend = [p for p in cola if p['id'] not in listos]
    if not pend:
        print('No quedan publicaciones en la cola. Hay que cargar la tanda siguiente.')
        return
    p = pend[0]
    print(f"Publicando {p['id']} · Día {p['dia']} · {p['categoria']} · {p['titulo']}")
    media = publicar(p)
    if media:
        hecho.append({'id': p['id'], 'titulo': p['titulo'], 'media_id': media,
                      'fecha': time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})
        json.dump(hecho, open('publicado.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print('Publicado. ID:', media, '· Quedan', len(pend) - 1)


if __name__ == '__main__':
    main()
