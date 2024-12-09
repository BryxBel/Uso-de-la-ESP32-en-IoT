#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "net/sock/udp.h"
#include "net/ipv6/addr.h"
#include "thread.h"
#include "xtimer.h"
#include "dht.h"

#define SERVER_MSG_QUEUE_SIZE   (8)
#define SERVER_BUFFER_SIZE      (64)
#define DHT_PIN GPIO_PIN(0, 4)
#define SEND_INTERVAL (5 * US_PER_SEC)

static dht_t sensor;
static const dht_params_t dht_params = {
    .pin = DHT_PIN,
    .type = DHT11
};

/* Function for sending UDP data */
int udp_send(int argc, char **argv) {
    if (argc != 3) {
        puts("Usage: startsensor <ipv6-addr> <port>");
        return -1;
    }

    sock_udp_ep_t remote = { .family = AF_INET6 };
    if (ipv6_addr_from_str((ipv6_addr_t *)&remote.addr, argv[1]) == NULL) {
        puts("Error: invalid IPv6 address.");
        return 1;
    }

    remote.port = atoi(argv[2]);
    if (ipv6_addr_is_link_local((ipv6_addr_t *)&remote.addr)) {
        gnrc_netif_t *netif = gnrc_netif_iter(NULL);
        remote.netif = (uint16_t)netif->pid;
    }

    if (dht_init(&sensor, &dht_params) != 0) {
        puts("Error initializing DHT sensor.");
        return -1;
    }

    while (1) {
        char data[20];
        int16_t temp = 0, hum = 0;

        if (dht_read(&sensor, &temp, &hum) == 0) {
            snprintf(data, sizeof(data), "%d,%d", temp / 10, hum / 10);
            if (sock_udp_send(NULL, data, strlen(data), &remote) < 0) {
                puts("Error: failed to send data.");
            } else {
                printf("Data sent: %s\n", data);
            }
        } else {
            puts("Error reading from DHT sensor.");
        }

        xtimer_usleep(SEND_INTERVAL);
    }

    return 0;
}

/* Function for starting UDP server */
int udp_server(int argc, char **argv) {
    if (argc != 2) {
        puts("Usage: udps <port>");
        return -1;
    }

    uint16_t port = atoi(argv[1]);
    sock_udp_t sock;
    sock_udp_ep_t server = { .port = port, .family = AF_INET6 };

    if (sock_udp_create(&sock, &server, NULL, 0) < 0) {
        puts("Error: failed to create UDP server.");
        return -1;
    }

    char server_buffer[SERVER_BUFFER_SIZE];
    puts("UDP server started successfully.");

    while (1) {
        sock_udp_ep_t remote;
        int res = sock_udp_recv(&sock, server_buffer, sizeof(server_buffer) - 1, SOCK_NO_TIMEOUT, &remote);

        if (res < 0) {
            puts("Error receiving data.");
        } else if (res == 0) {
            puts("No data received.");
        } else {
            server_buffer[res] = '\0'; // Ensure null-terminated string
            printf("Received data: %s\n", server_buffer);
        }
    }

    return 0;
}
