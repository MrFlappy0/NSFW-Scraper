# 🔥 NSFW SCRAPER 🔥

**Un outil de scraping asynchrone ultra-robuste, conçu pour contourner les protections anti-bot (Cloudflare), automatiser l'extraction d'albums multimédias et gérer des téléchargements segmentés haute performance.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![AsyncIO](https://img.shields.io/badge/AsyncIO-Enabled-success.svg)](https://docs.python.org/3/library/asyncio.html)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📋 Table des Matières
1. [À Propos du Projet](#-à-propos-du-projet)
2. [Fonctionnalités Avancées](#-fonctionnalités-avancées)
3. [Architecture Technique](#-architecture-technique)
4. [Prérequis & Dépendances](#-prérequis--dépendances)
5. [Installation & Structure](#-installation--structure)
6. [Guide d'Utilisation](#-guide-dutilisation)
7. [Sécurité, Faux Headers & Résilience](#-sécurité-faux-headers--résilience)
8. [Gestion des Logs & Base de Données](#-gestion-des-logs--base-de-données)

---

## 🎯 À Propos du Projet

**NSFW SCRAPER** est un script Python autonome orienté CLI (Interface en Ligne de Commande) combinant la puissance de `yt-dlp`, `gallery-dl` et un moteur de téléchargement segmenté personnalisé sous `aiohttp`. 

Pensé pour les environnements hautes performances (comme les configurations SSD/NVMe sur macOS/Linux), il intègre des mécanismes stricts de contournement de Cloudflare, un système de reprise après incident (Resume) via SQLite, et une vérification d'intégrité vidéo en temps réel via `ffprobe`.

---

## 🚀 Fonctionnalités Avancées

* **🛡️ Contournement Intelligent de Cloudflare & Anti-Freeze :**
  * Rotation dynamique et aléatoire de User-Agents récents (Chrome/Firefox sous macOS et Windows).
  * Usurpation d'adresses IP locales (`X-Forwarded-For`, `X-Real-IP`) et entêtes `Referer` personnalisés.
  * **Spinner visuel asynchrone** intégré pour patienter sans effet "gel" de la console pendant les phases d'analyse lourdes.
  * Auto-mise à jour automatique des extracteurs critiques (`gallery-dl`, `yt-dlp`) au démarrage pour parer immédiatement aux patchs de sécurité des hébergeurs (ex: Bunkr).

* **⚡ Téléchargement "Cruise Control" (Multi-Workers) :**
  * Téléchargement en parallèle par segments (chunks de 10 Mo) via une file d'attente `asyncio`.
  * Assemblage direct sur disque et validation vidéo rigoureuse (`ffprobe`) pour supprimer instantanément les fichiers corrompus ou tronqués.

* **💾 Persistance SQLite & Reprise Intelligente :**
  * Suivi précis de chaque média via une base de données locale (`PENDING`, `DOWNLOADING`, `COMPLETED`, `FAILED`).
  * Évite les doublons : si un fichier est déjà présent et intègre, il est automatiquement ignoré.

* **🔀 Double Moteur Intégré :**
  * **Mode Streaming :** Utilisation native de `yt-dlp` optimisée pour la fusion vidéo/audio (`bestvideo+bestaudio/best` -> `.mp4`).
  * **Mode Albums / Furtif :** Extraction d'URL via `gallery-dl` combinée au moteur de téléchargement segmenté `aiohttp`.

---

## 🏗️ Architecture Technique

```text
┌────────────────────────────────────────────────────────┐
│                     Menu Principal                     │
└───────────┬────────────────────────────────┬───────────┘
            │                                │
            ▼ (Option 1)                     ▼ (Option 2)
    ┌──────────────┐                 ┌──────────────┐
    │   yt-dlp     │                 │  gallery-dl  │ + 🔄 Spinner Visuel
    └──────┬───────┘                 └──────┬───────┘
           │                                │
           ▼                                ▼
    ┌──────────────┐                 ┌──────────────┐
    │  Stockage    │                 │ Base SQLite  │ ──> (Dédoublonnage & Suivi)
    │  Streaming   │                 └──────┬───────┘
    └──────────────┘                        │
                                            ▼
                                     ┌──────────────┐
                                     │   Aiohttp    │ ──> (Workers Parallèles & Chunks)
                                     └──────┬───────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │   FFprobe    │ ──> (Vérification d'intégrité vidéo)
                                     └──────┬───────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │  Assemblage  │ ──> Sortie NVMe (`scrap/downloads/`)
                                     └──────────────┘
