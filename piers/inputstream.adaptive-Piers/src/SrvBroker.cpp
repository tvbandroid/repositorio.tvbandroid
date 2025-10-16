/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "SrvBroker.h"

#include "CompKodiProps.h"
#include "CompResources.h"
#include "CompSettings.h"

using namespace ADP;

CSrvBroker::CSrvBroker() = default;
CSrvBroker::~CSrvBroker() = default;

void CSrvBroker::Initialize()
{
  m_compKodiProps = std::make_unique<KODI_PROPS::CCompKodiProps>();
  m_compResources = std::make_unique<RESOURCES::CCompResources>();
  m_compSettings = std::make_unique<SETTINGS::CCompSettings>();
}

void CSrvBroker::InitStage1(const std::map<std::string, std::string>& kodiProps)
{
  m_compKodiProps->InitStage1(kodiProps);
}

void CSrvBroker::InitStage2(adaptive::AdaptiveTree* tree)
{
  m_compResources->InitStage2(tree);
}

void CSrvBroker::Deinitialize()
{
  m_compKodiProps.reset();
  m_compResources.reset();
  m_compSettings.reset();
}
