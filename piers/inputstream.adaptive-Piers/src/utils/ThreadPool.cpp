/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "ThreadPool.h"

void UTILS::THREAD::ThreadPool::Stop()
{
  {
    std::lock_guard lock(m_mutex);
    m_isStopped = true;
  }

  m_condVar.notify_all();

  for (const auto& executor : m_executors)
    executor->Join();
}

void UTILS::THREAD::ThreadPool::Reset()
{
  Stop();
  m_activeExecutors = 0;
  m_executors.clear();
  m_isStopped = false;
}

std::optional<std::function<void()>> UTILS::THREAD::ThreadPool::TakeTask()
{
  std::unique_lock lock(m_mutex);

  m_condVar.wait(lock, [this]() { return !m_taskQueue.empty() || m_isStopped; });

  if (m_isStopped)
    return {};

  ++m_activeExecutors;
  auto func = std::move(m_taskQueue.front());
  m_taskQueue.pop();
  return {std::move(func)};
}

void UTILS::THREAD::ThreadPool::TaskFinished()
{
  std::lock_guard lock(m_mutex);
  --m_activeExecutors;
}

UTILS::THREAD::ThreadPool::Executor::Executor(ThreadPool& threadPool) : m_threadPool(&threadPool)
{
  m_thread = std::thread(&Executor::Run, this);
}

void UTILS::THREAD::ThreadPool::Executor::Join()
{
  m_thread.join();
}

void UTILS::THREAD::ThreadPool::Executor::Run()
{
  while (true)
  {
    auto f = m_threadPool->TakeTask();
    if (!f)
      return;
    (*f)();
    m_threadPool->TaskFinished();
  }
}

UTILS::THREAD::ThreadPool UTILS::THREAD::GlobalThreadPool;
