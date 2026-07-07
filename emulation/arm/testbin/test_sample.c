/*
 * test_sample.c — BINARIO ARM BENIGNO DE PRUEBA (TFM IoT Sandbox, CP-2)
 * ============================================================================
 *
 *  ⚠  ESTO NO ES MALWARE.  Es un binario de prueba deliberadamente BENIGNO y
 *     totalmente transparente cuyo único fin es VALIDAR la tubería de telemetría
 *     de la sandbox (strace + tcpdump + inotify) descrita en ADR-004/005.
 *     No borra nada, no persiste, no cifra, no descarga ni ejecuta nada.
 *     Se ejecuta SIEMPRE dentro del invitado QEMU, nunca en el host.
 *
 *  Reproduce, de forma controlada, los tres comportamientos que la sandbox debe
 *  ser capaz de observar en una muestra real de malware IoT:
 *
 *    (a) SYSCALLS   — hace una batería de llamadas al sistema visibles
 *                     (getpid, getuid, uname, open/read/write/close, stat, ...).
 *    (b) FICHEROS   — crea y escribe un fichero marcador en /tmp
 *                     (los eventos de FS los captura inotifywait dentro del invitado).
 *    (c) RED        — intenta (i) resolver un dominio por DNS y (ii) abrir un socket
 *                     TCP saliente hacia una IP:puerto fijos. En la sandbox de CP-2 la
 *                     red va con `restrict=on` (SLIRP), así que el intento FALLA a
 *                     propósito, pero los paquetes (consulta DNS + SYN TCP) SÍ salen por
 *                     la NIC del invitado y quedan capturados en el pcap. Eso es lo que
 *                     importa: registrar el *intento* de C2, como haría el análisis real.
 *
 *  Compilación (estática, ARM hard-float EABI5), hecha por build_rootfs.sh:
 *      arm-linux-gnueabihf-gcc -static -O2 -march=armv7-a -mfpu=vfpv3-d16 \
 *          -mfloat-abi=hard -o test_sample test_sample.c
 *
 *  El destino "C2" y el dominio son valores de laboratorio no enrutables/de ejemplo
 *  (documentación RFC 5737 / RFC 2606), nunca una infraestructura real.
 * ============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

/* --- Parámetros de laboratorio (NO son infraestructura real) --------------- */
#define TMP_MARKER   "/tmp/iot_sandbox_marker.txt"   /* fichero benigno en /tmp   */
#define FAKE_DOMAIN  "c2.sandbox-test.example"       /* dominio de ejemplo RFC2606*/
#define FAKE_C2_IP   "198.51.100.23"                 /* IP de doc. RFC5737 (TEST-NET-2) */
#define FAKE_C2_PORT 4444                            /* puerto "C2" de juguete    */
#define DNS_SERVER   "10.0.2.3"                      /* resolver de QEMU SLIRP    */

/* (a) Batería de syscalls benignas fácilmente visibles en strace.log */
static void do_syscalls(void)
{
    struct utsname uts;
    struct stat st;

    printf("[test_sample] (a) syscalls: pid=%d uid=%d\n", (int)getpid(), (int)getuid());
    if (uname(&uts) == 0)
        printf("[test_sample]     uname: %s %s %s\n", uts.sysname, uts.release, uts.machine);
    /* stat de un fichero típico solo para generar tráfico de syscalls */
    if (stat("/etc/hostname", &st) == 0)
        printf("[test_sample]     stat(/etc/hostname) size=%ld\n", (long)st.st_size);
    (void)sleep(0);   /* nanosleep visible; no bloquea */
}

/* (b) Crea/escribe un fichero marcador en /tmp -> lo detecta inotifywait */
static void do_file_write(void)
{
    printf("[test_sample] (b) fs: escribiendo %s\n", TMP_MARKER);
    FILE *f = fopen(TMP_MARKER, "w");
    if (!f) { perror("[test_sample]     fopen"); return; }
    fprintf(f, "IoT sandbox benign test marker\n");
    fprintf(f, "epoch=%ld pid=%d\n", (long)time(NULL), (int)getpid());
    fclose(f);
    /* un chmod para generar otro evento de FS (attrib) */
    chmod(TMP_MARKER, 0644);
}

/*
 * Construye una consulta DNS mínima (tipo A) para FAKE_DOMAIN y la envía por UDP
 * al resolver. Garantiza que aparezca un paquete DNS en el pcap aunque getaddrinfo
 * (con libc estática) no emita nada. No espera respuesta (en la sandbox no la hay).
 */
static void do_manual_dns(void)
{
    unsigned char pkt[512];
    int len = 0;

    /* Cabecera DNS: ID=0x1337, RD=1, 1 pregunta */
    pkt[len++] = 0x13; pkt[len++] = 0x37;   /* ID              */
    pkt[len++] = 0x01; pkt[len++] = 0x00;   /* flags: RD=1      */
    pkt[len++] = 0x00; pkt[len++] = 0x01;   /* QDCOUNT=1        */
    pkt[len++] = 0x00; pkt[len++] = 0x00;   /* ANCOUNT=0        */
    pkt[len++] = 0x00; pkt[len++] = 0x00;   /* NSCOUNT=0        */
    pkt[len++] = 0x00; pkt[len++] = 0x00;   /* ARCOUNT=0        */

    /* QNAME: FAKE_DOMAIN codificado por etiquetas (len + bytes) */
    const char *d = FAKE_DOMAIN;
    while (*d) {
        const char *dot = strchr(d, '.');
        int label = dot ? (int)(dot - d) : (int)strlen(d);
        pkt[len++] = (unsigned char)label;
        memcpy(&pkt[len], d, label);
        len += label;
        d += label;
        if (dot) d++; else break;
    }
    pkt[len++] = 0x00;                       /* fin del nombre  */
    pkt[len++] = 0x00; pkt[len++] = 0x01;    /* QTYPE = A        */
    pkt[len++] = 0x00; pkt[len++] = 0x01;    /* QCLASS = IN      */

    int s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) { perror("[test_sample]     socket(udp)"); return; }
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port   = htons(53);
    inet_pton(AF_INET, DNS_SERVER, &sa.sin_addr);
    printf("[test_sample]     enviando consulta DNS A para %s -> %s:53\n", FAKE_DOMAIN, DNS_SERVER);
    if (sendto(s, pkt, len, 0, (struct sockaddr *)&sa, sizeof(sa)) < 0)
        perror("[test_sample]     sendto(dns)");
    close(s);
}

/* (c) Intento de conexión saliente: DNS + TCP SYN hacia el "C2" de laboratorio */
static void do_network(void)
{
    printf("[test_sample] (c) red: intento de contacto con C2 (esperado que falle en sandbox)\n");

    /* (c.1) resolución de dominio: intento por libc (best-effort) + paquete DNS manual */
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    int gai = getaddrinfo(FAKE_DOMAIN, "80", &hints, &res);
    printf("[test_sample]     getaddrinfo(%s) -> %s\n", FAKE_DOMAIN,
           gai == 0 ? "ok" : gai_strerror(gai));
    if (res) freeaddrinfo(res);
    do_manual_dns();   /* garantiza un paquete DNS en el pcap */

    /* (c.2) socket TCP saliente con timeout corto (no bloquear el análisis) */
    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { perror("[test_sample]     socket(tcp)"); return; }
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port   = htons(FAKE_C2_PORT);
    inet_pton(AF_INET, FAKE_C2_IP, &sa.sin_addr);

    /* timeout de envío/recepción para que el SYN salga y no se cuelgue */
    struct timeval tv = { .tv_sec = 3, .tv_usec = 0 };
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    printf("[test_sample]     connect() TCP -> %s:%d\n", FAKE_C2_IP, FAKE_C2_PORT);
    int rc = connect(s, (struct sockaddr *)&sa, sizeof(sa));
    if (rc == 0)
        printf("[test_sample]     conectado (inesperado en sandbox aislada)\n");
    else
        printf("[test_sample]     connect fallo (esperado): %s\n", strerror(errno));
    close(s);
}

int main(void)
{
    printf("==== test_sample: binario ARM BENIGNO de prueba (IoT sandbox CP-2) ====\n");
    do_syscalls();     /* (a) */
    do_file_write();   /* (b) */
    do_network();      /* (c) */
    printf("==== test_sample: fin (benigno, sin efectos persistentes) ====\n");
    return 0;
}
